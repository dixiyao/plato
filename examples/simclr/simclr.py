"""
The implementation for the SimCLR [1] method.

The official code: https://github.com/google-research/simclr

The third-party code: https://github.com/PatrickHua/SimSiam

Our implementation relys on:
 https://github.com/spijkervet/SimCLR.git

Reference:

[1]. https://arxiv.org/abs/2002.05709

"""

import simclr_net

from plato.trainers import self_sl as ssl_trainer
from plato.clients import ssl_simple as ssl_client
from plato.servers import fedavg


def main():
    """ A Plato federated learning training session using the FedRep algorithm. """
    trainer = ssl_trainer.Trainer
    simclr_model = simclr_net.SimCLR()
    client = ssl_client.Client(model=simclr_model, trainer=trainer)
    server = fedavg.Server(model=simclr_model, trainer=trainer)

    server.run(client)


if __name__ == "__main__":
    main()