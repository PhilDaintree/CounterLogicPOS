README

Counter Logic POS

webERP's strengths are it's accessibility from anywhere, it's robust backend accounting, procurement, multi-currency, stock management etc. However, it is plainly unsuitable as the basis for interaction with customers, there is no facility to scan barcodes to enter items into a sale, calculate change, open a cash-drawer, print receipts automatically when a transaction is completed.

This is where CounterLogic POS comes in, it has all these facilities expected of a modern Point of Sale system and is completely integrated with webERP.

Any number of independent CounterLogic POS systems (lanes) can run simultaneously and together webERP and CounterLogic form an advanced integrated Retail Management System.

POS lanes could be installed in any part of the world each operating in different currencies all integrated to a single webERP installation in a truly global and local business.

Commercial integrated retail management systems that could currently work under such conditions are very expensive and complex propositions indeed.

The back office functions of receiving inventory, entering supplier invoices, printing customer statements, label printing etc can all be done currently from webERP. However, webERP lacks the interactivity that a client side GUI can provide with integration to scanner/printer/cash drawer. webERP also requires continuous connectivity to the web server hosting the webERP installation, this may not always be possible.

CounterLogic POS provides the solution to webERP's shortcomings as a customer facing solution.
With CounterLogic POS there is no requirement for 24x7 connectivity to the webERP server and it provides a fully interactive, optimised sales terminal that minimises the keying and maximises the accuracy of both sale and cash receipt recording.

NB: Counter Logic POS cannot currently deal with webERP's seriliased or controlled items.

Architecture

Counter Logic POS is write in Python and uses libusb-1.0 and pyusb for communication with USB receipt printers and from the receipt printer to open a cashdrawer. There are two applications:
- CounterLogic.py - the application itself
- Linker.py - this provides the link for downloading the esssential stock, customer, prices data from the webERP installation and then sending back the transactions recorded in Counter Logic POS. The Linker.py can be initiated from CounterLogic.py or as a scheduled recurring job with parameters to either download and refresh the data or upload transactions. Setting it up to run on a scheduled basis avoids the need to remember!

Documentation

Although the application is intuitive and simple, documentation is provided under the doc folder.

Licence
This software is free for all :-)
However, if you make improvements please submit a pull request.
