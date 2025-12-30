## Important Notice

This is a fork from the "pre-release" software for beta testers of Roastmaster for iOS10. This will NOT working with prior versions of Roastmaster (9 and below).
This fork converts the C++ Arduino code to Python3 for use in Raspberry Pi or other Linux based SBCs. 

## Roastmaster RDP Probe Host (SBC)

Roastmaster_RDP_Probe_Host is a customizable Single Board Computer (SBC) application to send sensor readings via the Roastmaster Datagram Protocol (RDP) to Roastmaster iOS over a WiFi Network, developed by Rainfrog Inc. 

Roastmaster is coffee roasting toolkit and data logging software, in which users can log temperature data during their coffee roasting sessions. This logging can be done either manually or via separate electronic thermocouple reading "clients".

The RDP Protocol is an OpenSource communications protocol created by Rainfrog, Inc. for the purpose of standardizing the transmission of roasting information to Roastmaster.

Roastmaster_RDP_Probe_Host and the RDP protocol can function either alone, or alongside other hosts. Each host has a unique Serial Number string to identify itself to the server, which can negotiate simple SYN/ACK handshaking. So, we (the client) need only perform a multicast with our Serial Number and a synch (SYN) request, and await a response from Roastmaster (the server) in the form of an acknowledgement (ACK).

Once the ACK has been received, we commence sending our thermocouple data to the server's (Roastmaster's) IP address.

## Code Development

Python code is currently in development and is in the develop branch of this fork. 

## Acknowledgements

Danny Hall (Rainfrog, Inc.) - Thanks for all the support and amazing launching point!

Evan Graham - Thanks for your incredibly imaginative solution to a seemingly insurmountable enigma by developing the first working prototype for getting digital readings from a rotating Gene Cafe drum

Robert Swift - Thanks for your impetus, vision and code prototyping
