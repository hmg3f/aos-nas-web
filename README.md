# Server Setup
Install Ubuntu or Debian to either a physical hardware or a virtual machine. Alternatively, a docker configuration can be found in `host_conf` which may help with getting a docker container set up. The machine must have an SSH daemon installed and running; it should be installed by default. Start the service using `sudo systemctl enable --now ssh`.

# Ansible
The `site.yml` file is an Ansible playbook which installs all the necessary components and configurations to the server. Alternatively, check the `site_conf` directory for the necessary files.

# Instructions for running application on an Ubuntu Virtual Machine

If you don't have an Ubuntu VM already, then download .iso file from Ubuntu's site: https://ubuntu.com/download/desktop

Create virtual machine using your virtual machine platform of choice.

Once the VM is running, follow the instructions below to run the project.

Navigate to the location you want the clone of the project to go.
`git clone https://github.com/hmg3f/aos-nas-web`

Install project dependencies:
`sudo apt install fuse libfuse-dev build-essential python3-dev pkgconf borgbackup libssl-dev liblz4-dev libzstd-dev libxxhash-dev libacl1-dev -y`

Install python virtual environment
`sudo apt install python3.12-venv`

Create python virtual environment
`python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt`

As of now, we have to manually clone the code for the borg backup functionality:
`git clone https://github.com/spslater/borgapi
cp -r borgapi/borgapi <path-to>/aos-nas-web/.venv/lib/python3.13/site-packages/`

or, depending on your python version

`cp -r borgapi/borgapi ~/Desktop/aos-nas-web/.venv/lib/python3.12/site-packages/`

Run the application:
`cd app
python3 app.py`

Once the application is running, the terminal will provide the IP address it is running on. Access that IP in your web browser to interact with the project.
