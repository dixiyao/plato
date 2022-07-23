"""
A basic federated learning client with homomorphic encryption support
"""

import logging
import random
import time
import sys
import torch
import numpy as np
import pickle
from dataclasses import dataclass
from typing import overload

from plato.algorithms import registry as algorithms_registry
from plato.clients import simple
from plato.config import Config
from plato.datasources import registry as datasources_registry
from plato.processors import registry as processor_registry
from plato.processors.model_encrypt import Processor as encrpt_processor
from plato.samplers import registry as samplers_registry
from plato.trainers import registry as trainers_registry
from plato.utils import fonts, homo_enc

class Client(simple.Client):
    """A basic federated learning client who sends simple weight updates."""

    def __init__(self,
                 model=None,
                 datasource=None,
                 algorithm=None,
                 trainer=None):
        super().__init__(model = model, datasource = datasource, algorithm = algorithm, trainer = trainer)

        self.encrypt_ratio = Config().clients.encrypt_ratio
        self.random_mask = Config().clients.random_mask

        self.attack_prep_dir = f"{Config().data.datasource}_{Config().trainer.model_name}_{self.encrypt_ratio}"
        if self.random_mask:
            self.attack_prep_dir += "_random"

        self.checkpoint_path = Config().params['checkpoint_path']
        self.model_buffer = []
    
    def get_exposed_weights(self):
        model_name = Config().trainer.model_name
        
        est_filename = f"{self.checkpoint_path}/{self.attack_prep_dir}/{model_name}_est_{self.client_id}.pth"
        return homo_enc.get_est(est_filename)

    def compute_mask(self, latest_weights, gradients):
        exposed_flat = self.get_exposed_weights()
        device = exposed_flat.device
        
        latest_flat = torch.cat([torch.flatten(latest_weights[name]) for _, name 
                                    in enumerate(latest_weights)]) 
        # Store the plain model weights
        plain_filename = f"{self.checkpoint_path}/{self.attack_prep_dir}/{Config().trainer.model_name}_plain_{self.client_id}.pth"
        with open(plain_filename, 'wb') as plain_file:
            pickle.dump(latest_flat, plain_file)

        if self.random_mask:
            rand_mask = random.sample(range(len(exposed_flat)), int(self.encrypt_ratio * len(exposed_flat)))
            return torch.tensor(rand_mask)
        gradient_list = [torch.flatten(gradients[name]).to(device) for _, name
                                                    in enumerate(gradients)]
        grad_flat = torch.cat(gradient_list) 

        
        
        delta = exposed_flat - latest_flat
        product = delta * grad_flat
        
        _, indices = torch.sort(product, descending = True)
        mask_len = int(self.encrypt_ratio * len(indices))
    
        return indices[:mask_len].clone().detach()


    async def payload_to_arrive(self, response):
        assert self.comm_simulation
        self.current_round = response['current_round']
        self.client_id = response['id']

        payload_filename = response['payload_filename']
        with open(payload_filename, 'rb') as payload_file:
            self.server_payload = pickle.load(payload_file)

        payload_size = sys.getsizeof(pickle.dumps(self.server_payload))

        logging.info(
            "[%s] Received %.2f MB of payload data from the server (simulated).",
            self, payload_size / 1024**2)

        if self.current_round % 2 != 0:
        
            #print(response)
            # Update (virtual) client id for client, trainer and algorithm
            

            self.process_server_response(response)

            self.configure()

            logging.info("[Client #%d] Selected by the server.", self.client_id)

            self.server_payload = self.inbound_processor.process(
            self.server_payload)

            if not hasattr(Config().data,
                        'reload_data') or Config().data.reload_data:
                self.load_data()
            await self.start_training()

            mask_proposal = self.compute_mask(self.algorithm.extract_weights(),
                                              self.trainer.gradient)
            # Send mask_proposal to server
            await self.send(mask_proposal, process = False)

        else:
            mask = self.server_payload
            client_id, report, payload = self.model_buffer.pop(0)
            assert client_id == response['id']

            # No training happens in this round.
            report.training_time = 0
            await self.sio.emit('client_report', {
            'id': client_id,
            'report': pickle.dumps(report)
            })
            for processor in self.outbound_processor.processors:
                if isinstance(processor, encrpt_processor):
                    processor.encrypt_mask = mask
            await self.send(payload, process = True)

    async def start_training(self):
        """ Overwrite training function. """
        self.load_payload(self.server_payload)
        self.server_payload = None

        report, payload = await self.train()

        # Sending the client report as metadata to the server (payload to follow)
        await self.sio.emit('client_report', {
            'id': self.client_id,
            'report': pickle.dumps(report)
        })

        self.model_buffer.append((self.client_id, report, payload))


    async def send(self, payload, process = True):
        """Sending the client payload to the server using simulation, S3 or socket.io."""
        # First apply outbound processors, if any
        if process:
            payload = self.outbound_processor.process(payload)

        if self.comm_simulation:
            # If we are using the filesystem to simulate communication over a network
            model_name = Config().trainer.model_name if hasattr(
                Config().trainer, 'model_name') else 'custom'
            checkpoint_path = Config().params['checkpoint_path']
            payload_filename = f"{checkpoint_path}/{model_name}_client_{self.client_id}.pth"
            with open(payload_filename, 'wb') as payload_file:
                pickle.dump(payload, payload_file)

            logging.info(
                "[%s] Sent %.2f MB of payload data to the server (simulated).",
                self,
                sys.getsizeof(pickle.dumps(payload)) / 1024**2)