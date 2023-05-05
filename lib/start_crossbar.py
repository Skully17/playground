from os.path import dirname
from crossbar import run

# The __main__ method should always be able to find the Crossbar config directory
# The conventional location is as below.
run_dir = dirname(__file__)
crossbar_config_dir = f"{run_dir}/.crossbar"


if __name__ == '__main__':
    print(f"Starting Crossbar with config_dir: {crossbar_config_dir}")
    run()
