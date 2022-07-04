"""
A federated learning server using federated averaging to train Actor-Critic models.

To run this example:

python examples/customized/custom_server.py -c examples/customized/server.yml
"""

import logging
import asyncio

from plato.servers import fedavg
from plato.config import Config
import pickle
import numpy as np
import csv
import random

class A2CServer(fedavg.Server):
    """ Federated learning server using federated averaging to train Actor-Critic models. """
    """ A custom federated learning server. """

    def __init__(self, algorithm_name, env_name, model = None, trainer = None, algorithm = None):
        super().__init__(trainer = trainer, algorithm = algorithm, model = model)
        self.algorithm_name = algorithm_name
        self.env_name = env_name
        logging.info("A custom server has been initialized.")
        
    async def federated_averaging(self, updates):
        """Aggregate weight updates from the clients using federated averaging."""

        weights_received = self.compute_weight_deltas(updates)

        if Config().server.percentile_aggregate:
            
            print("-----------------------")
            print("WE ARE AGGREGATING BASED ON PERCENTILE!")
            print("-----------------------")

            percentile = min(Config().server.percentile + Config().server.percentile_increase * self.current_round, 100)
            
            metric_list = self.create_loss_lists(updates)
            print("Metric list", metric_list)
            metric_percentile = np.percentile(np.array(metric_list), percentile)
            clients_selected_size = len([i for i in metric_list if i <= metric_percentile])

            # Save percentile to files
            path = Config().results.results_dir +"/"+Config().results.file_name+"_percentile_"+Config().server.percentile_aggregate
            self.save_files(path, metric_percentile)
        else:
            print("-----------------------")
            print("WE ARE NOT AGGREGATING BASED ON PERCENTILE!")
            print("-----------------------")
          
        # Perform weighted averaging for both Actor and Critic
        actor_avg_update = {
            name: self.trainer.zeros(weights.shape)
            for name, weights in weights_received[0][0].items()
        }
        critic_avg_update = {
            name: self.trainer.zeros(weights.shape)
            for name, weights in weights_received[0][1].items()
        }
        
        for i, update in enumerate(weights_received):
            __, report, __, __ = updates[i] 
            client_id = report.client_id
            client_path = f'{Config().results.results_dir}_seed_{Config().server.random_seed}/{Config().results.file_name}_client_saved'
            #Config().results.results_dir +"/"+Config().results.file_name+"_client_saved"

            update_from_actor, update_from_critic = update
            
            
            if not Config().server.percentile_aggregate:
                self.save_files(f'{client_path}{"_Fed_avg"}', client_id)
                for name, delta in update_from_actor.items():
                    actor_avg_update[name] += delta * 1.0/Config().clients.per_round

                for name, delta in update_from_critic.items():
                    critic_avg_update[name] += delta * 1.0/Config().clients.per_round
            else:
                metric = self.select_metric(report)
                # TODO: weight of delta should be the weightage of the client 1/number of clients choosen to be aggregated
                # TODO: know how many are >= percentile to have the correct ratio next to deltas
                print("Metric", metric)
                print("Metric percentile", metric_percentile)
                
               # if metric <= metric_percentile:
                if (client_id == 1 and self.current_round >= 1 and self.current_round <= 3) \
                or ((client_id == 1 or client_id == 2) and self.current_round > 3 and self.current_round <= 6) \
                or ((client_id == 1 or client_id == 2 or client_id == 3) and self.current_round > 6):
                    print("Client %s is choosen" % str(client_id))
                    if self.current_round <= 3:
                        clients_selected_size = 1
                    elif self.current_round > 3 and self.current_round <= 6:
                        clients_selected_size = 2
                    else:
                        clients_selected_size = 3
                    self.save_files(f'{client_path}{"_percentile"}', client_id)
                    for name, delta in update_from_actor.items():
                        actor_avg_update[name] += delta * 1.0/clients_selected_size
                    for name, delta in update_from_critic.items():
                        critic_avg_update[name] += delta * 1.0/clients_selected_size
            
            # Yield to other tasks in the server
            await asyncio.sleep(0)
        
        return actor_avg_update, critic_avg_update

    def save_files(self, file_path, data):
        #To avoid appending to existing files, if the current roudn is one we write over
        with open(f'{file_path}.csv', 'w'if self.current_round == 1 else 'a') as filehandle:
            writer = csv.writer(filehandle)
            writer.writerow([data])

    def select_metric(self, report):
        if Config().server.percentile_aggregate == "actor_loss":
            return report.actor_loss
        elif Config().server.percentile_aggregate == "critic_loss":
            return report.critic_loss
        elif Config().server.percentile_aggregate == "actor_grad":
            return report.actor_grad
        elif Config().server.percentile_aggregate == "critic_grad":
            return report.critic_grad
        elif Config().server.percentile_aggregate == "actor_fisher":
            return report.actor_fisher
        elif Config().server.percentile_aggregate == "critic_fisher":
            return report.critic_fisher



    def create_loss_lists(self, updates):
        """Creates the lost lists"""
        loss_list = []
        for (_, report, _, _) in updates:
            if Config().server.percentile_aggregate == "actor_loss":
                loss_list.append(report.actor_loss)
            elif Config().server.percentile_aggregate == "critic_loss":
                loss_list.append(report.critic_loss)
            elif Config().server.percentile_aggregate == "actor_grad":
                loss_list.append(report.actor_grad)
            elif Config().server.percentile_aggregate == "critic_grad":
                loss_list.append(report.critic_grad)
            elif Config().server.percentile_aggregate == "actor_fisher":
                loss_list.append(report.actor_fisher)
            elif Config().server.percentile_aggregate == "critic_fisher":
                loss_list.append(report.critic_fisher)

        return loss_list


    def save_to_checkpoint(self):
        """ Save a checkpoint for resuming the training session. """
        checkpoint_path = Config.params['checkpoint_path']

        copy_algorithm = self.algorithm_name
        if '_' in copy_algorithm:
            copy_algorithm= copy_algorithm.replace('_', '')
        
        env_algorithm = f'{self.env_name}{copy_algorithm}'
        model_name = env_algorithm
     
        filename = f"{model_name}_{self.current_round}"
        logging.info("[%s] Saving the checkpoint to %s/%s.", self,
                     checkpoint_path, filename)
        self.trainer.save_model(filename, checkpoint_path)
        self.save_random_states(self.current_round, checkpoint_path)

        # Saving the current round in the server for resuming its session later on
        with open(f"{checkpoint_path}/current_round_seed_{Config().server.random_seed}.pkl",
                  'wb') as checkpoint_file:
            pickle.dump(self.current_round, checkpoint_file)


    def save_random_states(self, round_to_save, checkpoint_path):
        """ Saving the random states in the server for resuming its session later on. """
        states_to_save = [
            f'numpy_prng_state_{round_to_save}_seed_{Config().server.random_seed}', 
            f'prng_state_{round_to_save}_seed_{Config().server.random_seed}'
        ]

        variables_to_save = [
            np.random.get_state(),
            random.getstate(),
        ]

        for i, state in enumerate(states_to_save):
            with open(f"{checkpoint_path}/{state}.pkl",
                      'wb') as checkpoint_file:
                pickle.dump(variables_to_save[i], checkpoint_file)

    
    def restore_random_states(self, round_to_restore, checkpoint_path):
        """ Restoring the numpy.random and random states from previously saved checkpoints
            for a particular round.
        """
        states_to_load = [ f'numpy_prng_state_{round_to_restore}_seed_{Config().server.random_seed}', 
            f'prng_state_{round_to_restore}_seed_{Config().server.random_seed}']
        variables_to_load = {}

        for i, state in enumerate(states_to_load):
            with open(f"{checkpoint_path}/{state}_{round_to_restore}.pkl",
                      'rb') as checkpoint_file:
                variables_to_load[i] = pickle.load(checkpoint_file)

        numpy_prng_state = variables_to_load[0]
        self.prng_state = variables_to_load[1]

        np.random.set_state(numpy_prng_state)
        random.setstate(self.prng_state)