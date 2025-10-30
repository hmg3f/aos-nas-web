# Server Setup
Install Ubuntu or Debian to either a physical hardware or a virtual machine. Alternatively, a docker configuration can be found in `host_conf` which may help with getting a docker container set up. The machine must have an SSH daemon installed and running; it should be installed by default. Start the service using `sudo systemctl enable --now ssh`.

# Ansible
The `site.yml` file is an Ansible playbook which installs all the necessary components and configurations to the server. Alternatively, check the `site_conf` directory for the necessary files.
