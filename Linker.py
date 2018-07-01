#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import sqlite3
import xmlrpclib
import httplib
import gettext
import codecs
import datetime
#import time
import hashlib
import urllib
import zipfile

Version = '0.40'

class TimeoutTransport(xmlrpclib.Transport):
	timeout = 1800.0
	def set_timeout(self, timeout):
		self.timeout = timeout
	def make_connection(self, host):
		h = httplib.HTTPConnection(host, strict=False, port=80, timeout=self.timeout)
		return h

if getattr(sys, 'frozen', False):
    InstallDirectory = os.path.dirname(sys.executable)
elif __file__:
    InstallDirectory = os.path.dirname(__file__)

if len(sys.argv) == 2:
	print InstallDirectory + '/data/CounterLogic.sqlite'
   #connect to the SQLite database named CounterLogic.sqlite
	db = sqlite3.connect(InstallDirectory + '/data/CounterLogic.sqlite',detect_types=sqlite3.PARSE_DECLTYPES)
	db.row_factory = sqlite3.Row
	# db database handle for sqlite3 calls
	#Get the configuration of this install and store in a dict Config

	#Get the configuration parameters
	result = db.cursor()
	result.execute("SELECT configname, configvalue FROM config")
	#Create an associative array of parameters configname:confvalue
	Config=dict()
	print 'Version'  + ' ' + str(Version)
	for row in result:
		print row['configname'], row['configvalue']
		Config[row['configname']] = row['configvalue']

	print Config['DefaultDateFormat']
	#Start a new log file
	if os.path.isfile(InstallDirectory + '/data/Linker.log') :
		if os.path.isfile(InstallDirectory + '/data/Linker_old.log'):
			os.unlink(InstallDirectory + '/data/Linker_old.log')
		os.rename(InstallDirectory + '/data/Linker.log',InstallDirectory + '/data/Linker_old.log')

	LogFileHandle = codecs.open(InstallDirectory + '/data/Linker.log', 'w','utf-8')
	LogFileHandle.write('Linker initiated with ' + sys.argv[1] + ' at ' + str(datetime.datetime.now()) + "\n")

	x_server = xmlrpclib.Server(Config['webERPXmlRpcServer'],verbose=True)

	CustomerDetails = dict()
	result = db.cursor()
	result.execute("SELECT debtorsmaster.debtorno, name, currcode, salestype, holdreason, dissallowinvoices, paymentterms, discount, creditlimit, discountcode, taxgroupid FROM debtorsmaster INNER JOIN holdreasons ON debtorsmaster.holdreason=holdreasons.reasoncode INNER JOIN custbranch ON debtorsmaster.debtorno=custbranch.debtorno WHERE custbranch.debtorno=? AND custbranch.branchcode=? ",(Config['DebtorNo'], Config['BranchCode']))
	Row = result.fetchone()
	if Row != None:
		CustomerDetails['debtorno'] = Row['debtorno']
		CustomerDetails['name'] = Row['name']
		CustomerDetails['currcode'] = Row['currcode']
		CustomerDetails['salestype'] = Row['salestype']
		CustomerDetails['holdreason'] = Row['holdreason']
		CustomerDetails['paymentterms'] = Row['paymentterms']
		CustomerDetails['discount'] = Row['discount']
		CustomerDetails['creditlimit'] = Row['creditlimit']
		CustomerDetails['discountcode'] = Row['discountcode']
		CustomerDetails['taxgroupid'] = Row['taxgroupid']
		CustomerDetails['branchcode'] = Config['BranchCode']

		print (CustomerDetails['name'])

	#-------------------------------------------- SENDING TRANSACTIONS TO webERP -----------------------

	if( sys.argv[1] == 'send' ):

		Message =  "Sending transactions to webERP!"
		print Message.encode('utf-8')
		LogFileHandle.write(Message + "\n")
		#This function sends all unsent transactions from the POS to webERP using the webERP xml-rpc API
		#Config is a dict that holds all the configuration parameters

		Result = db.cursor()
		OrderDetails = db.cursor()
		CheckForCharges = db.cursor()
		UpdateSent = db.cursor()
		OrderHeaderDetails = dict()
		OrderLineDetails = dict()

		#Get all the unsent invoice  transactions (type=10 and ovamount>0) waiting in the POS
		Result.execute('SELECT DISTINCT debtortrans.transno, debtortrans.type, debtortrans.debtorno, debtortrans.branchcode, brname, tpe, debtortrans.trandate FROM debtortrans INNER JOIN custbranch ON debtortrans.debtorno=custbranch.debtorno AND debtortrans.branchcode=custbranch.branchcode INNER JOIN stockmoves ON debtortrans.transno=stockmoves.transno AND debtortrans.type=stockmoves.type WHERE (stockmoves.qty*stockmoves.price)>0 AND sent=0 AND debtortrans.type=10')
		Rows = Result.fetchall()

		for Row in Rows:
			#Setup the data for the sales order header for this transaction
			OrderHeaderDetails['debtorno'] = Row['debtorno']
			OrderHeaderDetails['branchcode'] = Row['branchcode']

			if Config['DefaultDateFormat']=='d/m/Y':
				OrderHeaderDetails['orddate'] = Row['trandate'].strftime('%d/%m/%Y')
			elif Config['DefaultDateFormat']=='d.m.Y':
				OrderHeaderDetails['orddate'] = Row['trandate'].strftime('%d/%m/%Y')
			elif Config['DefaultDateFormat']=='m.d.Y':
				OrderHeaderDetails['orddate'] = Row['trandate'].strftime('%m/%d/%Y')
			elif Config['DefaultDateFormat']=='m/d/Y':
				OrderHeaderDetails['orddate'] = Row['trandate'].strftime('%m/%d/%Y')
			elif Config['DefaultDateFormat']=='Y/m/d':
				OrderHeaderDetails['orddate'] = Row['trandate'].strftime('%Y/%m/%d')

			print 'Order Date = '+str(OrderHeaderDetails['orddate'])
			OrderHeaderDetails['deliverydate'] = OrderHeaderDetails['orddate']
			OrderHeaderDetails['confirmeddate'] = OrderHeaderDetails['orddate']
			OrderHeaderDetails['datepackingslipprinted'] = OrderHeaderDetails['orddate']
			OrderHeaderDetails['deliverto'] = Row['brname']
			OrderHeaderDetails['ordertype'] = Row['tpe']
			OrderHeaderDetails['printedpackingslip'] = 1
			OrderHeaderDetails['fromstkloc'] = Config['Location']
			OrderHeaderDetails['customerref'] = 'POS-' + Config['POS_ID'] + ' ' + str(Row['transno'])
			OrderHeaderDetails['shipvia'] = Config['DefaultShipper']
			OrderDetails.execute('SELECT count(*) FROM stockmoves WHERE type=10 AND qty>0 AND transno=?',(Row['transno'],))
			NumberOfChargesRow = OrderDetails.fetchone()
			if NumberOfChargesRow[0] > 0:
				OrderSuccessful = True #assume the best
				try:
					SalesOrder = x_server.weberp.xmlrpc_InsertSalesOrderHeader(OrderHeaderDetails,Config['webERPuser'],Config['webERPpwd'])
				except xmlrpclib.Fault, err:
					Message =  "XML-RPC Fault inserting order header code: %d" % err.faultCode
					print Message.encode('utf-8')
					LogFileHandle.write(Message + "\n")
					print "Fault string: %s" % err.faultString
					OrderSuccessful = False
					sys.exit()

				#Now get the data for the sales order items
				if SalesOrder[0]!=0:
					Message =  'FAILED on transaction ' + str(Row['transno']) + ' could not create sales order. Returned error : ' + str(SalesOrder[0])
					print Message.encode('utf-8')
					LogFileHandle.write(Message + "\n")
					OrderSuccessful = False
				else:
					Message = 'Transaction ' + str(Row['transno']) + ' order header number ' + str(SalesOrder[1]) + ' created successfully'
					print Message.encode('utf-8')
					LogFileHandle.write(Message + "\n")

					OrderDetails.execute('SELECT stockid, qty, price, discountpercent FROM stockmoves WHERE type=10 AND (price*qty)>0 AND transno=?',(Row['transno'],))
					OrderLines = OrderDetails.fetchall()
					for OrderLine in OrderLines:
						Message =  'order line ' + OrderLine['stockid']
						print Message.encode('utf-8')
						LogFileHandle.write(Message + "\n")

						OrderLineDetails['stkcode'] = OrderLine['stockid']
						OrderLineDetails['unitprice'] = OrderLine['price']
						OrderLineDetails['quantity'] = OrderLine['qty']
						OrderLineDetails['discountpercent'] = OrderLine['discountpercent']
						OrderLineDetails['itemdue'] = OrderHeaderDetails['orddate']
						OrderLineDetails['actualdispatchdate'] = OrderHeaderDetails['orddate']
						OrderLineDetails['orderno'] = SalesOrder[1]
						try:
							SalesOrderLine = x_server.weberp.xmlrpc_InsertSalesOrderLine(OrderLineDetails,Config['webERPuser'],Config['webERPpwd'])
						except xmlrpclib.Fault, err:
							Message =  "XML-RPC Fault inserting order line. Error code: %d" % err.faultCode
							print Message.encode('utf-8')
							LogFileHandle.write(Message + "\n")
							print "Fault string: %s" % err.faultString
							OrderSuccessful = False
						if SalesOrderLine[0]!=0:
							Message =  'FAILED on transaction ' + str(Row['transno']) + ' for ' + OrderLine['stockid'] + ' could not create sales order line . Returned error : ' + str(SalesOrderLine[0])
							print Message.encode('utf-8')
							LogFileHandle.write(Message + "\n")
							OrderSuccessful = False
						OrderLineDetails.clear()
					#end loop around the order lines

					#Now the order has been created produce the invoice for the whole order
					if OrderSuccessful ==True:
						InvoiceSuccessful = True
						try:
							InvoiceArray = x_server.weberp.xmlrpc_InvoiceSalesOrder(int(SalesOrder[1]),Config['webERPuser'],Config['webERPpwd'])
							if InvoiceArray[0]==0:
								Message =  'Invoice number ' + str(InvoiceArray[1]) + ' created'
								print Message.encode('utf-8')
								LogFileHandle.write(Message + "\n")
							else:
								Message =  'The following error occurred:' + str(InvoiceArray[0])
								print Message.encode('utf-8')
								LogFileHandle.write(Message + "\n")
								InvoiceSuccessful = False
						except xmlrpclib.Fault, err:
							Message =  "XML-RPC Fault creating invoice for order. Error code: %d" % err.faultCode
							print Message.encode('utf-8')
							LogFileHandle.write(Message + "\n")
							print "Fault string: %s" % err.faultString
							InvoiceSuccessful = False
							sys.exit()

						if InvoiceSuccessful == True:
							#Now check to see there are no returns on this transaction
							OrderDetails.execute('SELECT count(*) FROM stockmoves WHERE type=10 AND (price*qty)<0 AND transno=?',(Row['transno'],))
							NumberOfReturnsRow = OrderDetails.fetchone()
							if NumberOfReturnsRow[0] ==0:
								UpdateSent.execute('UPDATE debtortrans SET sent=1 WHERE type=10 AND transno=?',(Row['transno'],))
								db.commit()
							else:
								Message =  'There are' + str(NumberOfReturnsRow[0]) + 'returns in the sale'
								print Message.encode('utf-8')
								LogFileHandle.write(Message + "\n")
							#else need to process the return too with credit note in webERP
						#end if the Invoice was Successfully created
					#end if the Order details have been successfully created
				#end if the Order header was sucessfully created
			#end if there were charges (stockmoves) on the transaction
			OrderHeaderDetails.clear() #clear the dict holding the OrderHeaderDetails
		#End loop around order Headers for unset transactions

		#Now do any unset credit lines - returns
		CreditDetails = db.cursor() # for the line items
		CN_Header = dict() #To hold the credit note header for sending via XML-RPC
		CN_Line = dict() #To hold the credit note line - we will send an array of them
		AllocParameters=dict() # To hold the parameters for the allocation
		#Get all the unsent transactions waiting in the POS
		Result.execute('SELECT DISTINCT debtortrans.transno, debtortrans.debtorno, branchcode, trandate, ovamount, ovgst, salestype FROM debtortrans INNER JOIN stockmoves ON debtortrans.transno=stockmoves.transno INNER JOIN debtorsmaster ON debtortrans.debtorno=debtorsmaster.debtorno AND debtortrans.type=stockmoves.type WHERE sent=0 AND debtortrans.type=10 AND (stockmoves.qty*stockmoves.price)<0')

		CreditNotes = Result.fetchall()
		for CNote in CreditNotes:
			#Setup the data for the sales order header for this transaction
			CN_Header['debtorno'] = CNote['debtorno']
			CN_Header['branchcode'] = CNote['branchcode']
			CN_Header['trandate'] = CNote['trandate'].strftime('%Y-%m-%d')
			CN_Header['tpe'] = CNote['salestype']
			CN_Header['fromstkloc'] = Config['Location']
			CN_Header['customerref'] = 'POS-' + str(Config['POS_ID']) + ' ' + str(CNote['transno'])
			CN_Header['shipvia'] = Config['DefaultShipper']
			CreditDetails.execute('SELECT stockid, price, qty, discountpercent FROM stockmoves WHERE type=10 AND (price*qty)<0 AND transno=?',(CNote['transno'],))
			CreditLines =[] #create a list/array of credit note lines
			Credits = CreditDetails.fetchall()
			for Line in Credits:
				CN_Line['stockid'] = Line['stockid']
				CN_Line['price'] = Line['price']
				CN_Line['qty'] = Line['qty']
				CN_Line['discountpercent'] = Line['discountpercent']
				CreditLines.append(CN_Line)

			#Now send the header and lines to the XML-RPC method
			CN_Successful = True #always assume the best :-) .... but test for the worst
			try:
				CN_Array = x_server.weberp.xmlrpc_CreateCreditNote(CN_Header, CreditLines, Config['webERPuser'],Config['webERPpwd'])
				if CN_Array[0]==0:
					Message =  'Credit Note number ' + str(CN_Array[1]) + ' created'
					print Message.encode('utf-8')
					LogFileHandle.write(Message + "\n")
				else:
					Message =  'The following errors occurred:'
					print Message.encode('utf-8')
					LogFileHandle.write(Message + "\n")
					for error in  CN_Array:
						print error
						LogFileHandle.write(error)
					CN_Successful = False
			except xmlrpclib.Fault, err:
				Message =  "XML-RPC Fault creating credit note. Error code: %d" % err.faultCode
				print Message.encode('utf-8')
				LogFileHandle.write(Message + "\n")
				print "Fault string: %s" % err.faultString
				CN_Successful = False
				sys.exit()

			if CN_Successful == True:
				AllocParameters['debtorno'] = CNote['debtorno']
				AllocParameters['type'] = 11
				AllocParameters['transno'] = CN_Array[1]
				AllocParameters['customerref'] = 'POS-' + str(Config['POS_ID']) + ' ' + str(CNote['transno'])
				try:
					Alloc_Array = x_server.weberp.xmlrpc_AllocateTrans(AllocParameters, Config['webERPuser'],Config['webERPpwd'])
				except xmlrpclib.Fault, err:
					Message =  "XML-RPC Fault allocating the credit note. Error code: %d" % err.faultCode
					print Message.encode('utf-8')
					LogFileHandle.write(Message + "\n")
					print "Fault string: %s" % err.faultString
					sys.exit()
				UpdateSent.execute('UPDATE debtortrans SET sent=1 WHERE type=10 AND transno=?',(CNote['transno'],))
				db.commit()
		#end loop around the debtortrans with negative stockmoves in them which were unsent

		#OK now for the customer receipts
		Receipt = dict()
		#Receipt['debtorno'] - the customer code
		#Receipt['trandate'] - the date of the receipt in Y-m-d format
		#Receipt['amountfx'] - the amount in FX
		#Receipt['paymentmethod'] - the payment method of the receipt e.g. cash/EFTPOS/credit card
		#Receipt['bankaccount'] - the webERP bank account
		#Receipt['reference']
		Message =  'Now sending the customer receipts'
		print Message.encode('utf-8')
		LogFileHandle.write(Message + "\n")
		#Get all the unsent receipt transactions (type=12) waiting in the POS
		#There should be no payment method 9999 that will be recorded in the debtortrans for account charges - so these will not be sent to webERP
		Result.execute("SELECT transno, debtorno, trandate, ovamount, ovdiscount, paymentname, bankaccount, methodid FROM debtortrans INNER JOIN paymentmethods ON debtortrans.paymentmethod=paymentmethods.paymentid INNER JOIN bankpaymentmethod ON debtortrans.paymentmethod=bankpaymentmethod.methodid WHERE sent=0 AND type=12 AND methodid<>'9999'")
		Rows = Result.fetchall()
		for Row in Rows:
			#Setup the data for the XML-RPC method to insert the receipt
			Receipt['debtorno'] = Row['debtorno']
			Receipt['trandate'] = Row['trandate'].strftime('%Y-%m-%d')
			Receipt['amountfx'] = Row['ovamount']
			Receipt['reference'] = 'POS-' + str(Config['POS_ID']) + ' ' + str(Row['transno'])
			Receipt['paymentmethod'] = Row['paymentname']
			Receipt['bankaccount'] = Row['bankaccount']
			Receipt['discountfx'] = Row['ovdiscount']

			try:
				ReceiptResult = x_server.weberp.xmlrpc_InsertDebtorReceipt(Receipt,Config['webERPuser'],Config['webERPpwd'])
			except xmlrpclib.Fault, err:
				Message =  "XML-RPC Fault inserting customer receipt. Error Code : %d" % err.faultCode
				print Message.encode('utf-8')
				LogFileHandle.write(Message + "\n")
				print "Fault string: %s" % err.faultString
				sys.exit()

			if ReceiptResult[0]!=0:
				Message =  'FAILED on transaction ' + str(Row['transno']) + ' could not insert debtor receipt. Returned error(s) : '
				print Message.encode('utf-8')
				LogFileHandle.write(Message + "\n")
				for ErrorNo in ReceiptResult:
					print ErrorNo
					LogFileHandle.write(ErrorNo)
			else:
				Message =  'webERP Receipt no. ' + str(ReceiptResult[1]) + ' payment method ' + str(Receipt['paymentmethod']) + ' for ' + str(Receipt['amountfx']) + ' created successfully'
				print Message.encode('utf-8')
				LogFileHandle.write(Message + "\n")
				#Now need to do the allocation against the invoice
				AllocParameters['debtorno'] = Receipt['debtorno']
				AllocParameters['type'] = 12
				AllocParameters['transno'] = ReceiptResult[1]
				AllocParameters['customerref'] = Receipt['reference']
				try:
					Alloc_Array = x_server.weberp.xmlrpc_AllocateTrans(AllocParameters, Config['webERPuser'],Config['webERPpwd'])
				except xmlrpclib.Fault, err:
					Message =  "XML-RPC Fault allocating the receipt. Error code: %d" % err.faultCode
					print Message.encode('utf-8')
					LogFileHandle.write(Message + "\n")
					print "Fault string: %s" % err.faultString
					sys.exit()

				UpdateSent.execute('UPDATE debtortrans SET sent=1 WHERE type=12 AND transno=? AND paymentmethod=?',(Row['transno'],Row['methodid']))

			#end else the insert to webERP was sucessful
		#end loop around the un-sent receipt transactions

		db.commit()
		LogFileHandle.close()

	elif( sys.argv[1] == 'full' or sys.argv[1] == 'admin'):
		#if this file is there then make sure it is deleted - as it must be old
		if os.path.isfile(InstallDirectory + '/data/upload.sql.zip'):
			os.remove(InstallDirectory + '/data/upload.sql.zip')
		if os.path.isfile(InstallDirectory + '/data/POS.sql'):
			os.remove(InstallDirectory + '/data/POS.sql')

		try:
			MakePOSUploadFile = x_server.weberp.xmlrpc_CreatePOSDataFull(Config['DebtorNo'],Config['BranchCode'],Config['webERPuser'],Config['webERPpwd'])
		except xmlrpclib.Fault, err:
			ErrorMessage = "Fatal error could not create the POS upload file on the webERP server"
			print ErrorMessage
			LogFileHandle.write(ErrorMessage)
			print "XML-RPC Fault logging in error code: %d" % err.faultCode
			print "Fault string: %s" % err.faultString
		if MakePOSUploadFile == 1:
			ErrorMessage = "Failed to create the POS upload file on the webERP server"
			print ErrorMessage
			LogFileHandle.write(ErrorMessage)
			sys.exit()
		try:
			ReportsDirectoryArray = x_server.weberp.xmlrpc_GetReportsDirectory(Config['webERPuser'],Config['webERPpwd'])
		except xmlrpclib.Fault, err:
			ErrorMessage = "Fatal error could not get the webERP reports directory off the webERP server"
			print ErrorMessage
			LogFileHandle.write(ErrorMessage)
			print "XML-RPC Fault logging in error code: %d" % err.faultCode
			print "Fault string: %s" % err.faultString

		if ReportsDirectoryArray[0]==0:
			Message =  'Reports directory was retrieved as ' + ReportsDirectoryArray[1]['confvalue']
			print Message.encode('utf-8')
			LogFileHandle.write(Message + "\n")
			ReportsDirectory = ReportsDirectoryArray[1]['confvalue']
		else:
			ErrorMessage = "Fatal error could not get the webERP reports directory off the webERP server"
			print ErrorMessage
			LogFileHandle.write(ErrorMessage)

		#webERPXmlRpcServer will always end in 'api/api_xml-rpc.php'  - 19 characters - need to chop this off and add companies/weberp database name/reports/POS.sql.zip
		URLForUploadFile = Config['webERPXmlRpcServer'][:-19] + ReportsDirectory + '/POS.sql.zip'
		#NB the reports directory must be set to "reports" in the webERP install
		print 'The URL For Upload File is: ' + URLForUploadFile

		Upload = urllib.urlretrieve(URLForUploadFile, InstallDirectory + '/data/upload.sql.zip')
		print InstallDirectory + '/data/upload.sql.zip'
		#now to process the sql file against the db
		try:
			zf = zipfile.ZipFile(InstallDirectory + '/data/upload.sql.zip', 'r')
		except zipfile.BadZipfile:
			Message =  "The POS upload file was not created. Perhaps there is some error with the download path of the POS upload file. Or maybe the operating system is unable to save the downloaded file to the data folder under installation folder?"
			print Message.encode('utf-8')
			LogFileHandle.write(Message + "\n")
			sys.exit()

		zf.extractall(path=InstallDirectory + '/data')
		zf.close()
		#now delete the zip file once it has been extracted to /data/POS.sql
		os.remove(InstallDirectory + '/data/upload.sql.zip')
		UploadFile = open(InstallDirectory + '/data/POS.sql', 'r')
		result = db.cursor()
		for sql_line in UploadFile:
			print sql_line
			result.execute(sql_line)
		db.commit()
		UploadFile.close()


		try:
			DeletePOSFileOffServer = x_server.weberp. xmlrpc_DeletePOSData(Config['webERPuser'],Config['webERPpwd'])
		except xmlrpclib.Fault, err:
			ErrorMessage = "Fatal error could not unzip the compressed POS upload file"
			print ErrorMessage
			LogFileHandle.write(ErrorMessage)
			print "XML-RPC Fault logging in error code: %d" % err.faultCode
			print "Fault string: %s" % err.faultString
		if DeletePOSFileOffServer == 1:
			ErrorMessage = "Failed to delete the POS upload file off the webERP server"
			print ErrorMessage
			LogFileHandle.write(ErrorMessage)

		Message =  "Completed full upload of data via direct download from webERP server"
		print "\n\n"
		print Message.encode('utf-8')
		LogFileHandle.write(Message + "\n")
		os.remove(InstallDirectory + '/data/POS.sql')

		LogFileHandle.close()
	else:
		Message =  "Program must be called with either Linker.exe send or Linker.exe full"
		print Message.encode('utf-8')
		LogFileHandle.write(Message + "\n")
		LogFileHandle.close()

else:
	print "No argument was supplied when calling the program. It must be called with either  POSLinker send or POSLinker full"

#-------------------------------------END PROGRAM -----------------------------------------
