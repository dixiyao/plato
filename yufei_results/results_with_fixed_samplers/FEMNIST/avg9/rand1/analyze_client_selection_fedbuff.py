from http import client
import numpy as np
import matplotlib.pyplot as plt
#my_file = Path("/path/to/file")
"""
Read .out file and draw clients distribution figure
"""
with open('FedBuff_FEMNIST_lenet5_500_20eachRound_avg9_round150.out') as f:
    for line in f.readlines():

        if 'Selected clients' in line:
            loc = line.find('Selected clients')
            clients = line[loc + 19:]
            loc_end = clients.find(']')
            # output file saves selected clients set
            outf = open("fedbuff_selected_clients.txt", "a")
            outf.write(clients[0:loc_end])
            outf.write(', ')
            outf.close()

with open("fedbuff_selected_clients.txt") as f:
    client_set = []
    for line in f.readlines():
        print(line.split())
        fig, ax = plt.subplots()
        ax.hist(line.split(','), 500)
        #ax.xlabel('clinet_id')
        #ax.ylabel('# of being selected')
        #ax.title('async_selected_clients_distribution_rand1_round250')
        figure_file_name = 'fedbuff_selected_clients_distribution.pdf'
        plt.savefig(figure_file_name)