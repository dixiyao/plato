"""
Implementation of running multiples experiments with Slurm.


The type of the experiments should be provided by:
    - key

Thus, the scripts containing the key will be performed.


For example,
to submit all methods using MNIST dataset

python examples/contrastive_adaptation/submit_slurm_jobs.py -k MNIST


"""

import argparse
import glob
import os

current_path = "./"

methods_root_dir = os.path.join(current_path, "examples",
                                "contrastive_adaptation")

script_files_dir = os.path.join(methods_root_dir, "run_scripts")


def is_desired_file(key_word, file_name):
    """ Whether the file name is the desired file defiend by key. """

    # if key_word is all, all files are desired.
    if key_word == "all":
        return True
    if key_word in file_name:
        return True

    return False


if __name__ == '__main__':

    experiment_script_files_name = glob.glob(
        os.path.join(script_files_dir, "*.sh"))

    parser = argparse.ArgumentParser()
    parser.add_argument('-k',
                        '--key',
                        type=str,
                        default='all',
                        help='The key word of desired scripts.')

    args = parser.parse_args()

    key_word = args.key

    desired_files_path = [
        file_path for file_path in experiment_script_files_name
        if is_desired_file(key_word, file_path)
    ]
    for script_file_path in desired_files_path:

        print(f"Running script: {script_file_path}")
        os.system("sbatch %s" % script_file_path)