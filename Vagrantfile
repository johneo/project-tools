Vagrant::Config.run do |config|
  # Every Vagrant virtual environment requires a box to build off of.
  config.vm.box = "lucid32"

  # The url from where the 'config.vm.box' box will be fetched if it
  # doesn't already exist on the user's system.
  config.vm.box_url = "http://files.vagrantup.com/lucid32.box"

  # Assign this VM to a host only network IP, allowing you to access it
  # via the IP.
  config.vm.network :hostonly, "172.24.24.24"

  # Forward a port from the guest to the host, which allows for outside
  # computers to access the VM, whereas host only networking does not.

  config.vm.forward_port 80, 8080
  config.vm.forward_port 81, 7080

  # Share an additional folder to the guest VM.
  config.vm.share_folder("v2-data", "/project", "./")

  config.vm.customize ["modifyvm", :id, "--memory", "1024"]

end

