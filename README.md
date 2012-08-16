# Shadytel SIM Tools

## Creating JavaCard STK Applets

Use the hello-stk example to get started.

	$ mkdir javacard
	$ cd javacard
	$ git clone https://github.com/Shadytel/sim-tools.git
	$ git clone https://github.com/Shadytel/hello-stk.git
	$ cd hello-stk
	$ make
	
To install the applet onto a SIM card, first set the type of reader you are using.

	# For PCSC readers:
    $ export SHADYSIM_OPTIONS="--pcsc"

	# For USB-serial readers:
    $ export SHADYSIM_OPTIONS="--serialport /dev/ttyUSB0"

    $ make install
    
The shadysim tool has lots of other options.

    $ ./sim-tools/bin/shadysim --help