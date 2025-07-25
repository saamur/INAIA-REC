import os
from copy import deepcopy
from datetime import datetime

import numpy as np

import jax.tree
from flax.core import unfreeze

import flax.nnx as nnx
import pickle
import lzma

from algorithms.networks import ActorCritic, RecurrentActorCritic, StackedActorCritic, StackedRecurrentActorCritic
from algorithms.networks import RECActorCritic, RECRecurrentActorCritic, RECMLP

path_base = '/trained_agents/'

def construct_net_from_config(config, rng):
    if config['NETWORK'] == 'actor_critic':
        return ActorCritic(
            config['OBSERVATION_SPACE_SIZE'],
            config['ACTION_SPACE_SIZE'],
            activation=config['ACTIVATION'],
            net_arch=config.get('NET_ARCH'),
            act_net_arch=config.get('ACT_NET_ARCH'),
            cri_net_arch=config.get('CRI_NET_ARCH'),
            add_logistic_to_actor=config.get('LOGISTIC_FUNCTION_TO_ACTOR', False),
            rngs=rng
        )
    elif config['NETWORK'] == 'recurrent_actor_critic':
        return RecurrentActorCritic(
            config['OBSERVATION_SPACE_SIZE'],
            config['ACTION_SPACE_SIZE'],
            num_sequences=config['NUM_SEQUENCES'],
            activation=config['ACTIVATION'],
            lstm_activation=config['LSTM_ACTIVATION'],
            net_arch=config.get('NET_ARCH'),
            act_net_arch=config.get('ACT_NET_ARCH'),
            cri_net_arch=config.get('CRI_NET_ARCH'),
            lstm_net_arch=config.get('LSTM_NET_ARCH'),
            lstm_act_net_arch=config.get('LSTM_ACT_NET_ARCH'),
            lstm_cri_net_arch=config.get('LSTM_CRI_NET_ARCH'),
            add_logistic_to_actor=config.get('LOGISTIC_FUNCTION_TO_ACTOR', False),
            rngs=rng
        )
    else:
        raise ValueError('Invalid network name')

def construct_battery_net_from_config_multi_agent(config, rng, num_nets=None):

    if num_nets is None:
        num_nets = config['NUM_BATTERY_AGENTS']

    if config['NETWORK_TYPE_BATTERIES'] == 'actor_critic':
        return StackedActorCritic(
            num_nets,
            config['BATTERY_OBS_KEYS'],
            config['BATTERY_ACTION_SPACE_SIZE'],
            activation=config['ACTIVATION'],
            obs_keys_cri=config.get('BATTERY_OBS_KEYS_CRI', None),
            net_arch=(config['NET_ARCH_BATTERIES'] if 'NET_ARCH_BATTERIES' in config.keys() else config.get('NET_ARCH')),
            act_net_arch=(config['ACT_NET_ARCH_BATTERIES'] if 'ACT_NET_ARCH_BATTERIES' in config.keys() else config.get('ACT_NET_ARCH')),
            cri_net_arch=(config['CRI_NET_ARCH_BATTERIES'] if 'CRI_NET_ARCH_BATTERIES' in config.keys() else config.get('CRI_NET_ARCH')),
            add_logistic_to_actor=config.get('LOGISTIC_FUNCTION_TO_ACTOR', False),
            normalize=config['NORMALIZE_NN_INPUTS'],
            rngs=rng)
    elif config['NETWORK_TYPE_BATTERIES'] == 'recurrent_actor_critic':
        return StackedRecurrentActorCritic(
            num_nets,
            config['BATTERY_OBS_KEYS'],
            config['BATTERY_ACTION_SPACE_SIZE'],
            activation=config['ACTIVATION'],
            obs_is_seq=config['BATTERY_OBS_IS_SEQUENCE'],
            obs_keys_cri=config.get('BATTERY_OBS_KEYS_CRI', None),
            lstm_activation=config['LSTM_ACTIVATION'],
            net_arch=(config['NET_ARCH_BATTERIES'] if 'NET_ARCH_BATTERIES' in config.keys() else config.get('NET_ARCH')),
            act_net_arch=(config['ACT_NET_ARCH_BATTERIES'] if 'ACT_NET_ARCH_BATTERIES' in config.keys() else config.get('ACT_NET_ARCH')),
            cri_net_arch=(config['CRI_NET_ARCH_BATTERIES'] if 'CRI_NET_ARCH_BATTERIES' in config.keys() else config.get('CRI_NET_ARCH')),
            lstm_net_arch=(config['LSTM_NET_ARCH_BATTERIES'] if 'LSTM_NET_ARCH_BATTERIES' in config.keys() else config.get('LSTM_NET_ARCH')),
            lstm_act_net_arch=(config['LSTM_ACT_NET_ARCH_BATTERIES'] if 'LSTM_ACT_NET_ARCH_BATTERIES' in config.keys() else config.get('LSTM_ACT_NET_ARCH')),
            lstm_cri_net_arch=(config['LSTM_CRI_NET_ARCH_BATTERIES'] if 'LSTM_CRI_NET_ARCH_BATTERIES' in config.keys() else config.get('LSTM_CRI_NET_ARCH')),
            add_logistic_to_actor=config.get('LOGISTIC_FUNCTION_TO_ACTOR', False),
            normalize=config['NORMALIZE_NN_INPUTS'],
            rngs=rng
    )
    else:
        raise ValueError('Invalid network name')

def construct_rec_net_from_config_multi_agent(config, rng):
    if config['NETWORK_TYPE_REC'] == 'actor_critic':
        return RECActorCritic(config['REC_OBS_KEYS'],
                              config['REC_OBS_IS_LOCAL'],
                              config['NUM_BATTERY_AGENTS'],
                              config['ACTIVATION'],
                              rngs=rng,
                              obs_keys_cri=config.get('REC_OBS_KEYS_CRI', None),
                              net_arch=(config['NET_ARCH_REC'] if 'NET_ARCH_REC' in config.keys() else config.get('NET_ARCH', ())),
                              act_net_arch=(config['ACT_NET_ARCH_REC'] if 'ACT_NET_ARCH_REC' in config.keys() else config.get('ACT_NET_ARCH')),
                              cri_net_arch=(config['CRI_NET_ARCH_REC'] if 'CRI_NET_ARCH_REC' in config.keys() else config.get('CRI_NET_ARCH')),
                              passive_houses=config['PASSIVE_HOUSES'],
                              normalize=config['NORMALIZE_NN_INPUTS'],
                              non_shared_net_arch_before=config.get('NON_SHARED_NET_ARCH_REC_BEFORE', ()),
                              non_shared_net_arch_after=config.get('NON_SHARED_NET_ARCH_REC_AFTER', ()),
                              )
    elif config['NETWORK_TYPE_REC'] == 'recurrent_actor_critic':
        return RECRecurrentActorCritic(config['REC_OBS_KEYS'],
                                       config['REC_OBS_IS_LOCAL'],
                                       config['REC_OBS_IS_SEQUENCE'],
                                       config['NUM_BATTERY_AGENTS'],
                                       config['ACTIVATION'],
                                       rngs=rng,
                                       net_arch=(config['NET_ARCH_REC'] if 'NET_ARCH_REC' in config.keys() else config.get('NET_ARCH', ())),
                                       act_net_arch=(config['ACT_NET_ARCH_REC'] if 'ACT_NET_ARCH_REC' in config.keys() else config.get('ACT_NET_ARCH')),
                                       cri_net_arch=(config['CRI_NET_ARCH_REC'] if 'CRI_NET_ARCH_REC' in config.keys() else config.get('CRI_NET_ARCH')),
                                       lstm_net_arch=(config['LSTM_NET_ARCH_REC'] if 'LSTM_NET_ARCH_REC' in config.keys() else config.get('LSTM_NET_ARCH')),
                                       lstm_act_net_arch=(config['LSTM_ACT_NET_ARCH_REC'] if 'LSTM_ACT_NET_ARCH_REC' in config.keys() else config.get('LSTM_ACT_NET_ARCH')),
                                       lstm_cri_net_arch=(config['LSTM_CRI_NET_ARCH_REC'] if 'LSTM_CRI_NET_ARCH_REC' in config.keys() else config.get('LSTM_CRI_NET_ARCH')),
                                       lstm_activation=config['LSTM_ACTIVATION'],
                                       non_shared_net_arch_before=config.get('NON_SHARED_NET_ARCH_REC_BEFORE', ()),
                                       non_shared_net_arch_after=config.get('NON_SHARED_NET_ARCH_REC_AFTER', ()),
                                       share_lstm_batteries=config['SHARE_LSTM_BATTERIES'],
                                       passive_houses=config['PASSIVE_HOUSES'],
                                       normalize=config['NORMALIZE_NN_INPUTS'],
                                       )
    elif config['NETWORK_TYPE_REC'] == 'mlp':
        return RECMLP(config['REC_OBS_KEYS'],
                      config['REC_OBS_IS_LOCAL'],
                      config['NUM_BATTERY_AGENTS'],
                      config['ACTIVATION'],
                      rngs=rng,
                      net_arch=config.get('NET_ARCH_REC', ()),
                      passive_houses=config['PASSIVE_HOUSES'],
                      normalize=config['NORMALIZE_NN_INPUTS'],
                      non_shared_net_arch_before=config.get('NON_SHARED_NET_ARCH_REC_BEFORE', ()),
                      non_shared_net_arch_after=config.get('NON_SHARED_NET_ARCH_REC_AFTER', ()),
                )
    else:
        raise ValueError('Invalid network name')

def save_state(network, config, params: dict, val_info:dict=None, train_info:dict=None, env_type='normal', additional_info=''):
    dir_name = (datetime.now().strftime('%Y%m%d_%H%M%S') +
                '_lr_' + str(config.get('LR')) +
                '_tot_timesteps_' + str(config.get('TOTAL_TIMESTEPS')) +
                '_rl_sched_' + str(config.get('LR_SCHEDULE')) +
                '_' + env_type +
                '_' + config['NETWORK'])

    if additional_info != '':
        dir_name += '_' + additional_info

    os.makedirs(path_base + dir_name)

    _, state = nnx.split(network)

    with open(path_base + dir_name + '/state.pkl', 'wb') as file:
        pickle.dump(state, file)

    with open(path_base + dir_name + '/config.pkl', 'wb') as file:
        pickle.dump(config, file)

    params = deepcopy(params)
    del params['demand']['data']
    if 'generation' in params.keys():
        del params['generation']['data']
    if 'market' in params.keys():
        del params['market']['data']
    if 'temp_ambient' in params.keys():
        del params['temp_ambient']['data']

    with open(path_base + dir_name + '/params.pkl', 'wb') as file:
        pickle.dump(params, file)

    with open(path_base + dir_name + '/val_info.pkl', 'wb') as file:
        pickle.dump(val_info, file)

    with open(path_base + dir_name + '/train_info.pkl', 'wb') as file:
        pickle.dump(train_info, file)


def restore_state(path):

    with open(path + '/config.pkl', 'rb') as file:
        config = pickle.load(file)

    with open(path + '/params.pkl', 'rb') as file:
        params = pickle.load(file)

    network_shape = construct_net_from_config(config, nnx.Rngs(0))
    graphdef, abstract_state = nnx.split(network_shape)

    with open(path + '/state.pkl', 'rb') as file:
        state_restored = pickle.load(file)

    network = nnx.merge(graphdef, state_restored)

    with open(path + '/val_info.pkl', 'rb') as file:
        val_info = pickle.load(file)

    if os.path.isfile(path + '/train_info.pkl'):
        with open(path + '/train_info.pkl', 'rb') as file:
            train_info = pickle.load(file)
    else:
        train_info = None

    return network, config, params, train_info, val_info

def save_state_multiagent(directory, networks_batteries, network_rec, config: dict, world_metadata, train_info:dict=None, val_info:dict=None, is_checkpoint=False, num_steps=-1):

    if is_checkpoint:
        directory = directory + 'checkpoints/' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + str(num_steps) +  '/'

    if not os.path.exists(directory):
        os.makedirs(directory)

    _, state_batteries = nnx.split(networks_batteries)
    _, state_rec = nnx.split(network_rec)

    with lzma.open(directory + 'state_batteries.xz', 'wb') as file:
        pickle.dump(state_batteries, file)
    with lzma.open(directory + 'state_rec.xz', 'wb') as file:
        pickle.dump(state_rec, file)


    with lzma.open(directory + 'config.xz', 'wb') as file:
        pickle.dump(config, file)

    with lzma.open(directory + 'world_metadata.xz', 'wb') as file:
        pickle.dump(world_metadata, file)

    val_info = jax.tree.map(lambda x: np.array(x), val_info)

    with lzma.open(directory + 'val_info.xz', 'wb', preset=4) as file:
        pickle.dump(val_info, file)

    train_info = jax.tree.map(lambda x: np.array(x), train_info)

    with lzma.open(directory + 'train_info.xz', 'wb', preset=4) as file:
        pickle.dump(train_info, file)


def restore_state_multi_agent(path):

    with lzma.open(path + '/config.xz', 'rb') as file:
        config = pickle.load(file)

    config = unfreeze(config)

    if 'NORMALIZE_NN_INPUTS' not in config.keys():
        config['NORMALIZE_NN_INPUTS'] = False

    if 'NETWORK_TYPE_BATTERIES' not in config.keys():
        config['NETWORK_TYPE_BATTERIES'] = 'actor_critic'
    if 'NETWORK_TYPE_REC' not in config.keys():
        config['NETWORK_TYPE_REC'] = 'actor_critic'

    with lzma.open(path + '/world_metadata.xz', 'rb') as file:
        world_metadata = pickle.load(file)

    network_batteries_shape = construct_battery_net_from_config_multi_agent(config, nnx.Rngs(0), num_nets=config.get('NUM_RL_AGENTS'))
    graphdef_batteries, abstract_batteries_state = nnx.split(network_batteries_shape)

    with lzma.open(path + '/state_batteries.xz', 'rb') as file:
        state_batteries_restored = pickle.load(file)

    network_batteries = nnx.merge(graphdef_batteries, state_batteries_restored)

    if config.get('USE_REC_RULE_BASED_POLICY', False):
        network_rec = None
    else:
        network_rec_shape = construct_rec_net_from_config_multi_agent(config, nnx.Rngs(0))
        graphdef_rec, abstract_rec_state = nnx.split(network_rec_shape)

        with lzma.open(path + '/state_rec.xz', 'rb') as file:
            state_rec_restored = pickle.load(file)

        network_rec = nnx.merge(graphdef_rec, state_rec_restored)


    if os.path.isfile(path + '/train_info.xz'):
        with lzma.open(path + '/train_info.xz', 'rb') as file:
            train_info = pickle.load(file)
    else:
        train_info = None

    with lzma.open(path + '/val_info.xz', 'rb') as file:
        val_info = pickle.load(file)

    return network_batteries, network_rec, config, world_metadata, train_info, val_info
