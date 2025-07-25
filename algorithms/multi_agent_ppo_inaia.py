from time import time
from datetime import datetime

import jax
import jax.numpy as jnp
from jax.experimental import io_callback
import flax.nnx as nnx
import optax

from algorithms.wrappers import VecEnvJaxMARL

from algorithms.train_core import StackedOptimizer, ValidationLogger, TrainState, config_enhancer, networks_builder, schedule_builder, optimizer_builder, prepare_runner_state
from algorithms.train_core import collect_trajectories
from algorithms.train_core import calculate_gae_batteries
from algorithms.train_core import update_batteries_network
from algorithms.train_core import update_rec_network_inaia
from algorithms.train_core import test_networks

from algorithms.tqdm_custom import scan_tqdm as tqdm_custom
from ernestogym.envs.multi_agent.env import RECEnv
import algorithms.utils as utils


def make_train(config, env:RECEnv, network_batteries=None, network_rec=None, seed=123):

    print('PPO INAIA')

    config_enhancer(config, env, is_rec_ppo=False)

    env = VecEnvJaxMARL(env)

    network_batteries, network_rec = networks_builder(config, network_batteries, network_rec, seed)

    schedule_batteries = schedule_builder(config['LR_SCHEDULE_BATTERIES'],
                                          config['LR_BATTERIES'],
                                          config['NUM_ITERATIONS'] * config['NUM_EPOCHS_BATTERIES'] * config['NUM_MINIBATCHES_BATTERIES'] *
                                              config['NUM_CONSECUTIVE_ITERATIONS_BATTERIES']/(config['NUM_CONSECUTIVE_ITERATIONS_BATTERIES']+config['NUM_CONSECUTIVE_ITERATIONS_REC']),
                                          lr_end=config.get('LR_BATTERIES_MIN', 0.),
                                          frac_dynamic=config.get('FRACTION_DYNAMIC_LR_BATTERIES', 1.),
                                          frac_warmup=config.get('WARMUP_SCHEDULE_BATTERIES', 0.),
                                          )

    optimizer_batteries = optimizer_builder(config['OPTIMIZER_BATTERIES'], schedule_batteries,
                                            beta_adam=config.get('BETA_ADAM_BATTERIES', 0.9),
                                            momentum=config.get('MOMENTUM_BATTERIES', None))

    tx_bat = optax.chain(optax.clip_by_global_norm(config['MAX_GRAD_NORM']), optimizer_batteries)
    optimizer_batteries = StackedOptimizer(config['NUM_RL_AGENTS'], network_batteries, tx_bat)

    schedule_rec = schedule_builder(config['LR_SCHEDULE_REC'],
                                    config['LR_REC'],
                                    config['NUM_ITERATIONS'] * config['UPDATE_TIMES_REC'] *
                                        config['NUM_CONSECUTIVE_ITERATIONS_REC']/(config['NUM_CONSECUTIVE_ITERATIONS_BATTERIES']+config['NUM_CONSECUTIVE_ITERATIONS_REC']),
                                    lr_end=config.get('LR_REC_MIN', 0.),
                                    frac_dynamic=config.get('FRACTION_DYNAMIC_LR_REC', 1.),
                                    frac_warmup=config.get('WARMUP_SCHEDULE_REC', 0.),
                                    )

    optimizer_rec = optimizer_builder(config['OPTIMIZER_REC'], schedule_rec,
                                      beta_adam=config.get('BETA_ADAM_REC', 0.9),
                                      momentum=config.get('MOMENTUM_REC', None))

    if 'MAX_GRAD_NORM_REC' in config.keys():
        tx_rec = optax.chain(optax.clip_by_global_norm(config['MAX_GRAD_NORM_REC']), optimizer_rec)
    else:
        tx_rec = optimizer_rec

    optimizer_rec = nnx.Optimizer(network_rec, tx_rec)

    return env, network_batteries, optimizer_batteries, network_rec, optimizer_rec

# @partial(nnx.jit, static_argnums=(0, 1, 7, 8, 9, 11))
def train(env: RECEnv, config, world_metadata, network_batteries, optimizer_batteries, network_rec, optimizer_rec, rng, validate=True, freq_val=None, val_env=None,
              val_rng=None, val_num_iters=None, path_saving=None):

    actual_num_iterations = int(config['NUM_ITERATIONS'] * config.get('TRUNCATE_FRACTION', 1))

    if validate:
        if freq_val is None or val_env is None or val_rng is None or val_num_iters is None:
            raise ValueError(
                "'freq_val', 'val_env', 'val_rng' and 'val_num_iters' must be defined when 'validate' is True")

    dir_name = (datetime.now().strftime('%Y%m%d_%H%M%S') + '/')
    directory = path_saving + dir_name
    logger = ValidationLogger(config, world_metadata, directory, actual_num_iterations, freq_val)

    def update_val_info(val_info, train_state):
        logger.log_val(val_info, train_state)

    @tqdm_custom(0, 0, 1, actual_num_iterations, print_rate=1)
    def _update_step(runner_state, curr_iter):

        def update_rec(runner_state):
            env_state, last_obs_batteries = runner_state.env_state, runner_state.last_obs_batteries
            runner_state, losses_rec = update_rec_network_inaia(runner_state, env, config)

            if config['RESTORE_ENV_STATE_AFTER_REC_UPDATE']:
                runner_state = runner_state._replace(env_state=env_state, last_obs_batteries=last_obs_batteries)

            return runner_state

        def update_batteries(runner_state):
            runner_state, traj_batch, last_val_batteries, _ = collect_trajectories(runner_state, config,
                                                                                   env, config['NUM_STEPS'])

            advantages_batteries, targets_batteries = calculate_gae_batteries(traj_batch, last_val_batteries, config)

            runner_state.network_batteries.train()
            runner_state, total_loss_batteries = update_batteries_network(runner_state, traj_batch,
                                                                          advantages_batteries, targets_batteries,
                                                                          config['NUM_MINIBATCHES_BATTERIES'],
                                                                          config['MINIBATCH_SIZE_BATTERIES'],
                                                                          config['NUM_EPOCHS_BATTERIES'],
                                                                          config)
            runner_state.network_batteries.eval()

            return runner_state

        runner_state = nnx.cond(curr_iter % (config['NUM_CONSECUTIVE_ITERATIONS_BATTERIES'] + config['NUM_CONSECUTIVE_ITERATIONS_REC']) < config['NUM_CONSECUTIVE_ITERATIONS_REC'],
                                update_rec,
                                update_batteries,
                                runner_state)

        if validate:
            train_state = TrainState(*nnx.split((runner_state.network_batteries, runner_state.network_rec)))

            jax.lax.cond(curr_iter % freq_val == 0,
                         lambda: io_callback(update_val_info,
                                             None,
                                             test_networks(val_env, train_state, val_num_iters, config, val_rng, curr_iter=curr_iter, print_data=True),
                                             train_state,
                                             ordered=True),
                         lambda: None)

        return runner_state

    if config['NUM_RL_AGENTS'] > 0:
        network_batteries.eval()
    network_rec.eval()

    runner_state = prepare_runner_state(env, config, network_batteries, optimizer_batteries, network_rec,
                                            optimizer_rec, rng)

    scanned_update_step = nnx.scan(_update_step,
                                   in_axes=(nnx.Carry, 0),
                                   out_axes=nnx.Carry)

    scanned_update_step = nnx.jit(scanned_update_step)

    runner_state = scanned_update_step(runner_state, jnp.arange(actual_num_iterations))

    if config['NUM_RL_AGENTS'] > 0:
        runner_state.network_batteries.eval()
    runner_state.network_rec.eval()

    print('Saving...')

    t0 = time()

    logger.save_final(runner_state.network_batteries, runner_state.network_rec)

    print(f'Saving time: {t0 - time():.2f} s')

    if validate:
        return  runner_state, logger.val_infos
    else:
        return runner_state
