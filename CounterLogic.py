#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pygtk # python interface to GTK GUI widgets
pygtk.require('2.0')
import gtk # needed for GUI
import sqlite3 # needed for database storage in CounterLogic.sqlite file
import xmlrpclib # needed for querying webERP stock on hand query
import httplib # required for longer timeout on stock on hand query
import datetime # for formatting and handling dates
import gettext #translation system
import usb.core # required for receipt printing
import usb.util # required for receipt printing
#import usb.backend.libusb1 # required to ensure we only use libusb-1.0 under *nix
import subprocess #needed for the system command to run the Linker script
import os #needed to get the path of where the application is running from
import sys #needed to exit application
#import serial # needed for EFTPOS integration option to send data to the EFTPOS terminal

Version = '0.33'

gtk.rc_parse('CounterLogic.rc')

if getattr(sys, 'frozen', False):
   InstallDirectory = os.path.dirname(sys.executable)
elif __file__:
   InstallDirectory = sys.path[0]

print InstallDirectory
#Language = 'zh_CN'  #change this for alternative language
Language = 'en_GB'   #change this for alternative language
#Language = 'es_ES'   #change this for alternative language
Lang = gettext.translation('messages', InstallDirectory + '/Languages',languages=[Language],fallback=True)
Lang.install()


class TimeoutTransport(xmlrpclib.Transport): # required to extend timeout on xml-rpc calls
	timeout = 30.0
	def set_timeout(self, timeout):
		self.timeout = timeout
	def make_connection(self, host):
		h = httplib.HTTPConnection(host, timeout=self.timeout)
		return h

class CounterLogic: #The main application class - all happens here

	def delete_event(self, widget, event, data=None):
		# Change FALSE to TRUE and the main window will not be destroyed
		# with a "delete_event".
		return False

	def Dont_delete_event(self, widget, event, data=None):
		# Change FALSE to TRUE and the main window will not be destroyed
		# with a "delete_event".
		return True

	def destroy(self, widget, data=None):
		print _("destroy signal occurred")
		gtk.main_quit()

	def SearchItems (self, widget, data=None):
		# Populate it with data from the database
		result = self.db.cursor()
		if self.SearchField=="Item Code":
			#Manny mod
			#result.execute("SELECT stockmaster.stockid, barcode, description, taxcatid FROM stockmaster WHERE stockid LIKE ? LIMIT 40",('___' + self.Search_Entry.get_text(),))
			result.execute("SELECT stockmaster.stockid, barcode, description, taxcatid FROM stockmaster WHERE stockid LIKE ? LIMIT 40",('%' + self.Search_Entry.get_text() + '%',))
		elif self.SearchField=="Bar Code":
			result.execute("SELECT stockmaster.stockid, barcode, description, taxcatid FROM stockmaster WHERE barcode LIKE ? LIMIT 40",('%' + self.Search_Entry.get_text() + '%',))
		elif self.SearchField=="Description":
			result.execute("SELECT stockmaster.stockid, barcode, description, taxcatid FROM stockmaster WHERE description LIKE  ? LIMIT 150",('%' + self.Search_Entry.get_text() + '%',))

		#Clear any data in the ListStore
		self.ItemSearch_ListStore.clear()
		#Now populate it with the new result set
		i=0
		for Row in result:
			Price = self.GetPrice(Row['stockid'],Row['taxcatid'],1)
			self.ItemSearch_ListStore.append((Row['stockid'],Row['barcode'],Row['description'],Price))
			i+=1

		if i==0:
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('No items were found for this search.'))

	def RadioButtonClicked (self, widget, data=None):
		#sets the SearchField system parameter based on the Radio Button Clicked
		#Could be SearchField = 'Item Code' or 'Bar Code' or 'Description'
		self.SearchField = data
		self.Search_Entry.grab_focus()

	def SelectedItem (self, treeview, SelectedItem_Path, ViewColumn, Data=None):
		#When an item is selected - double clicked or space on row selected
		SelectedItem_Iter = self.ItemSearch_ListStore.get_iter(SelectedItem_Path)
		self.ScanCode_Entry.set_text(self.ItemSearch_ListStore.get_value(SelectedItem_Iter, self.ItemSearch['StockID']))
		self.PopulateScannedItem(self.MainWindow)
		self.ItemSearch_Dialog.destroy()

	def OpenSearchItemsDialog(self, widget, data=None):
		self.ItemSearch_Dialog = gtk.Dialog(_("Item Search"),self.MainWindow,gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

		RowHBox = gtk.HBox(homogeneous=False, spacing=5)
		#Pack the RowHBox into the VerticalBox below the menu
		self.ItemSearch_Dialog.vbox.pack_start(RowHBox, False, False, 2)
		RowHBox.show()

		Search_Label = gtk.Label(_("Enter Search:"))
		Search_Label.show()
		RowHBox.pack_start(Search_Label,False,False, 2)

		self.SearchField = 'Item Code' #set as default to search by Item Code

		self.Search_Entry = gtk.Entry()
		self.Search_Entry.set_width_chars(20)
		self.Search_Entry.set_editable(True)
		self.Search_Entry.connect('changed', self.SearchItems)
		self.Search_Entry.show()
		RowHBox.pack_start(self.Search_Entry,False,False, 2)

		RadioBox = gtk.HBox(False, 10)
		RadioBox.set_border_width(10)
		RowHBox.pack_start(RadioBox, True, True, 0)
		RadioBox.show()
		Search_Radio = gtk.RadioButton(None, _('Seach Item _Code'))
		Search_Radio.connect('toggled', self.RadioButtonClicked, 'Item Code')
		RadioBox.pack_start(Search_Radio, True, True, 0)
		Search_Radio.set_active(True)
		Search_Radio.show()

		Search_Radio = gtk.RadioButton(Search_Radio, _('Search _Bar code'))
		Search_Radio.connect('toggled', self.RadioButtonClicked, 'Bar Code')
		RadioBox.pack_start(Search_Radio, True, True, 0)
		Search_Radio.show()

		Search_Radio = gtk.RadioButton(Search_Radio, _('Search _Description'))
		Search_Radio.connect('toggled', self.RadioButtonClicked, 'Description')
		RadioBox.pack_start(Search_Radio, True, True, 0)
		Search_Radio.show()

		separator = gtk.HSeparator()
		RowHBox.pack_start(separator, False, True, 0)
		separator.show()

		self.ItemSearch = dict()
		self.ItemSearch['StockID'] = 0
		self.ItemSearch['BarCode'] = 1
		self.ItemSearch['Description'] = 2
		self.ItemSearch['Price'] = 3
		#Define a list store to hold the ItemSearch
		self.ItemSearch_ListStore = gtk.ListStore(str,str,str,float)

		#Define a Tree View to display them
		ItemSearch_TreeView = gtk.TreeView(self.ItemSearch_ListStore)
		ItemSearch_TreeView.connect('row_activated', self.SelectedItem, None)
		#Define the columns to hold the data
		StockID_col = gtk.TreeViewColumn(_('Item Code'))
		BarCode_col = gtk.TreeViewColumn(_('Bar Code'))
		Description_col = gtk.TreeViewColumn(_('Description'))
		Price_col = gtk.TreeViewColumn(_('Price'))

		#Add the colums to the TreeView
		ItemSearch_TreeView.append_column(StockID_col)
		ItemSearch_TreeView.append_column(BarCode_col)
		ItemSearch_TreeView.append_column(Description_col)
		ItemSearch_TreeView.append_column(Price_col)

		#Define the cells to hold the data
		StockID_cell = gtk.CellRendererText()
		StockID_cell.set_property('width',180)
		StockID_col.pack_start(StockID_cell,True)
		StockID_col.set_attributes(StockID_cell, text=self.ItemSearch['StockID'])

		BarCode_cell = gtk.CellRendererText()
		BarCode_cell.set_property('width',180)
		BarCode_col.pack_start(BarCode_cell,True)
		BarCode_col.set_attributes(BarCode_cell, text=self.ItemSearch['BarCode'])

		Description_cell = gtk.CellRendererText()
		Description_cell.set_property('width',400)
		Description_col.pack_start(Description_cell,True)
		Description_col.set_attributes(Description_cell, text=self.ItemSearch['Description'])

		Price_cell = gtk.CellRendererText()
		Price_cell.set_property('width',80)
		Price_cell.set_property('xalign', 1)
		Price_col.pack_start(Price_cell,True)
		Price_col.set_cell_data_func(Price_cell, self.FormatDecimalPlaces, self.ItemSearch['Price'])

		ItemSearch_TreeView.show()

		ItemSearch_ScrolledWindow = gtk.ScrolledWindow(hadjustment=None, vadjustment=None)
		ItemSearch_ScrolledWindow.set_border_width(10)
		ItemSearch_ScrolledWindow.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		ItemSearch_ScrolledWindow.set_size_request(1000,600)
		ItemSearch_ScrolledWindow.add (ItemSearch_TreeView)
		ItemSearch_ScrolledWindow.show()

		self.ItemSearch_Dialog.vbox.pack_start(ItemSearch_ScrolledWindow, True)
		Response = self.ItemSearch_Dialog.run()
		if Response == gtk.RESPONSE_ACCEPT:
			CurrentSelection = ItemSearch_TreeView.get_selection()
			(model, ItemIter) = CurrentSelection.get_selected()
			if ItemIter != None:
				self.ScanCode_Entry.set_text(self.ItemSearch_ListStore.get_value(ItemIter, self.ItemSearch['StockID']))
				self.PopulateScannedItem(self.MainWindow)
				self.ItemSearch_Dialog.destroy()
		elif Response == gtk.RESPONSE_REJECT:
			self.ItemSearch_Dialog.destroy()


	def PopulateScannedItem (self, widget, data=None):
		result = self.db.cursor()
		GotAnItem=False
		if len(self.ScanCode_Entry.get_text()) > 0:
			print self.ScanCode_Entry.get_text()
			#check against the database to retrieve the item based on a bar code scan
			result.execute("SELECT stockid, description, taxcatid, decimalplaces, discountcategory FROM stockmaster WHERE barcode=?",(self.ScanCode_Entry.get_text(),))
			for Row in result:
				GotAnItem=True #as we found a result
				self.AddItemToSale(Row)

		if GotAnItem==False:
			#OK so try to see if the scanned code was the item code not a bar code
			result.execute("SELECT stockid, description, taxcatid, decimalplaces, discountcategory FROM stockmaster WHERE stockid=?",(self.ScanCode_Entry.get_text(),))
			for Row in result:
				GotAnItem=True #as we found a result
				self.AddItemToSale(Row)

			if GotAnItem==False:
				self.ScanResult_Label.set_label(_('There is no item for ') + self.ScanCode_Entry.get_text())
				self.ScanCode_Entry.set_text('')

	def AddItemToSale(self, Row):
		DuplicateItem = False
		#Loop through the ListStore to see if the item is already on the sale */
		SaleLine_TreeIter = self.SaleEntryGrid_ListStore.get_iter_first()
		while SaleLine_TreeIter:
			StockID =  self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['SKU'])
			Quantity = self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['Quantity'])
			if Row['stockid']==StockID:
				DuplicateItem=True
				Quantity = Quantity+1
				self.SaleEntryGrid_ListStore.set_value(SaleLine_TreeIter,self.Col['Quantity'],Quantity)
				#Now recheck the price given the increased quantity - discountmatrix quantity break may kick in
				Price = self.GetPrice(Row['stockid'],Row['taxcatid'],Quantity)
				if Price < self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['SellPrice']) and self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['ManualPrice']) == False:
					self.SaleEntryGrid_ListStore.set_value(SaleLine_TreeIter,self.Col['SellPrice'],Price)

			#end if the scanned item is already on the sale
			SaleLine_TreeIter = self.SaleEntryGrid_ListStore.iter_next(SaleLine_TreeIter)
		# end loop through all items in the SalesEntryGrid_ListStore

		if DuplicateItem==False: #The scanned item was not already on the sale
			#Now get the price ... if we canp
			Price = self.GetPrice(Row['stockid'],Row['taxcatid'],1)
			NewRowIter = self.SaleEntryGrid_ListStore.append((Row['stockid'],Row['description'],Price,1,Price,Row['decimalplaces'],Row['taxcatid'], False, Row['discountcategory'],''))

		self.ScanCode_Entry.set_text('')
		self.RecalculateSaleTotal()
		self.ScanResult_Label.set_label(_('Item') + ' ' +  Row['stockid'] + ' ' + _('has been added to the sale.') + '  ')
		self.ScanCode_Entry.grab_focus()

	def GetPrice (self, StockID, TaxCatID, Quantity):
		result = self.db.cursor()
		#First look for a price for the specific customer
		SQLParameters = (StockID, self.CustomerDetails['salestype'], self.CustomerDetails['debtorno'])
		result.execute("SELECT MIN(price) AS lowestprice FROM prices WHERE stockid=? AND typeabbrev=? AND debtorno=?",SQLParameters)
		FoundPrice = False
		for Row in result:
			if Row['lowestprice'] != None:
				FoundPrice = True
				Price = Row['lowestprice']

		if FoundPrice == False:
			SQLParameters = (StockID, self.CustomerDetails['salestype'])
			result.execute("SELECT MIN(price) AS lowestprice FROM prices WHERE stockid=? AND typeabbrev=?",SQLParameters)
			for Row in result:
				if Row['lowestprice'] != None:
					FoundPrice = True
					Price = Row['lowestprice']

		if FoundPrice == False:
			SQLParameters = (StockID, self.DefaultSalesType)
			result.execute("SELECT MIN(price) AS lowestprice FROM prices WHERE stockid=? AND typeabbrev=?",SQLParameters)
			for Row in result:
				if Row['lowestprice'] != None:
					FoundPrice = True
					Price = Row['lowestprice']

		if FoundPrice == True:
			# Now check the discountmatrix - to see if any discount should be applied
			SQLParameters = (StockID, self.CustomerDetails['salestype'], Quantity)
			result.execute("SELECT MAX(discountrate) as maxdiscount FROM discountmatrix INNER JOIN stockmaster ON discountmatrix.discountcategory=stockmaster.discountcategory WHERE stockmaster.stockid=? AND salestype=? AND quantitybreak<=?", SQLParameters)

			for Row in result:
				if Row['maxdiscount'] != None:
					Price *= (1-Row['maxdiscount'])

			# now apply the taxes to the price retrieved to get the gross tax inclusive price

			Price *= (1+self.TaxRate[TaxCatID])
			#add 1 hundredth of a cent to ensure always rounding up to the next whole cent
			Price += 0.001
			#round the price to 2 decimal places
			Price =round(Price,2)
			return Price
		else:
			return 0


	def GetCustomerDetails(self, DebtorNo, BranchCode):
		CustomerDetails = dict()
		result = self.db.cursor()
		result.execute("SELECT debtorsmaster.debtorno, name, currcode, salestype, holdreason, dissallowinvoices, paymentterms, discount, creditlimit, discountcode, taxgroupid FROM debtorsmaster INNER JOIN holdreasons ON debtorsmaster.holdreason=holdreasons.reasoncode INNER JOIN custbranch ON debtorsmaster.debtorno=custbranch.debtorno WHERE custbranch.debtorno=? AND custbranch.branchcode=? ",(DebtorNo, BranchCode))
		Row = result.fetchone()
		if Row != None:
			if Row['dissallowinvoices']==1:
				CustomerDetails = False
				MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('The customer selected is on hold with credit control another customer must be selected') + ' ' + DebtorNo)
				MessageBox.run()
				MessageBox.destroy()
			else:
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
				CustomerDetails['branchcode'] = BranchCode

				# Need to get the tax details and make a dict of the taxes too
				result.execute("SELECT taxauthority, taxcatid FROM taxgrouptaxes INNER JOIN taxauthorities ON taxgrouptaxes.taxauthid=taxauthorities.taxid  INNER JOIN taxauthrates ON taxauthorities.taxid=taxauthrates.taxauthority INNER JOIN locations ON taxauthrates.dispatchtaxprovince=locations.taxprovinceid WHERE locations.loccode=? AND taxgrouptaxes.taxgroupid=? ORDER BY taxcatid,calculationorder",(self.Config['Location'], CustomerDetails['taxgroupid']))


				#self.TaxRate is an associative array with the key being the tax category and the value being the tax rate applicable for the tax category ... this could be the sum of any number of tax authorities rates
				self.TaxRate = dict()
				#Taxes is an assoc array with the key the tax category again but this time contains an array of the taxes applicable and the rate of each
				self.Taxes = dict()
				i=0
				for Row in result:
					try:
						self.TaxRate[Row['taxcatid']]==None
					except KeyError:
						self.TaxRate[Row['taxcatid']]=0
						self.Taxes[Row['taxcatid']]=dict()
					i+=1
					self.Taxes[Row['taxcatid']][Row['taxauthority']]=dict()

				#Need to deal with none - where the Location is invalid or no tax details have been imported
				if i==0:
					CustomerDetails = False
					MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('Either the tax rates are not set up or the inventory location set up in the option dialog are incorrect. Please correct the options, then logout and back in to try again.'))
					MessageBox.run()
					MessageBox.destroy()
					print _('Could not get tax set up - possibly incorrect location in options dialog')
					return CustomerDetails


				result.execute("SELECT taxauthority, taxcatid, taxrate, taxontax FROM taxgrouptaxes INNER JOIN taxauthorities ON taxgrouptaxes.taxauthid=taxauthorities.taxid  INNER JOIN taxauthrates ON taxauthorities.taxid=taxauthrates.taxauthority INNER JOIN locations ON taxauthrates.dispatchtaxprovince=locations.taxprovinceid WHERE locations.loccode=? AND taxgrouptaxes.taxgroupid=? ORDER BY taxcatid,calculationorder",(self.Config['Location'], CustomerDetails['taxgroupid']))

				#now go around again same query but with taxrate and taxOntax and calculate tax rates
				#Figure out the effective overall tax percentage for each tax category
				#Also record the rate for each tax authority/tax category required for stockmovetaxes

				for Row in result:
					print 'TaxCatID = ' + str(Row['taxcatid']) + ' rate = ' + str(Row['taxrate'])

					if Row['taxontax']==1: #if tax on tax add taxrate x current total of taxes
						self.TaxRate[Row['taxcatid']] += (Row['taxrate']*self.TaxRate[Row['taxcatid']])
					self.TaxRate[Row['taxcatid']] += Row['taxrate']  # add all taxes together for this taxgroup
					print _('New tax rate for this customer tax group/ location, for tax category') + ' ' + str(Row['taxcatid']) + ' = ' + str(self.TaxRate[Row['taxcatid']])
					self.Taxes[Row['taxcatid']][Row['taxauthority']]['Rate'] = Row['taxrate']
					self.Taxes[Row['taxcatid']][Row['taxauthority']]['TaxOnTax'] = Row['taxontax']
					self.Taxes[Row['taxcatid']][Row['taxauthority']]['Amount'] = 0

				print _('New tax rate for this customer tax group/ location') + ' = ' + str(self.TaxRate[Row['taxcatid']])

				return CustomerDetails
		else:
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('Customer details could not be retrieved for the customer') + ' ' + DebtorNo)
			MessageBox.run()
			MessageBox.destroy()
			CustomerDetails['debtorno'] = 'ANGRY'
			CustomerDetails['name'] = 'Not setup correctly'
			CustomerDetails['currcode'] = 'USD'
			CustomerDetails['salestype'] = ''
			CustomerDetails['holdreason'] = ''
			CustomerDetails['paymentterms'] = ''
			CustomerDetails['discount'] = 0
			CustomerDetails['creditlimit'] = 100
			CustomerDetails['discountcode'] = ''
			CustomerDetails['taxgroupid'] = ''
			CustomerDetails['branchcode'] = 'ANGRY'
			return CustomerDetails
			print _('Customer is not valid - all sales must have a valid customer')

	def RecalculateSaleTotal (self):
		SaleLine_TreeIter = self.SaleEntryGrid_ListStore.get_iter_first()
		self.SaleTotal = 0
		self.TaxTotal = 0
		result = self.db.cursor()

		while SaleLine_TreeIter:

			Quantity = self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['Quantity'])
			TaxCatID = self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['TaxCatID'])
			StockID = self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['SKU'])

			if self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['ManualPrice']) == False:
				Price = self.GetPrice(StockID,TaxCatID,Quantity)
				self.SaleEntryGrid_ListStore.set_value(SaleLine_TreeIter, self.Col['SellPrice'],Price)
			else:
				Price = self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['SellPrice'])

			LineTotal = Price * Quantity
			self.SaleEntryGrid_ListStore.set_value(SaleLine_TreeIter,self.Col['LineTotal'],LineTotal)
			try:
				LineTaxRate = self.TaxRate[TaxCatID]
			except:
				LineTaxRate = 0
			self.TaxTotal += (LineTotal*LineTaxRate/(1+LineTaxRate))
			self.SaleTotal += LineTotal
			SaleLine_TreeIter = self.SaleEntryGrid_ListStore.iter_next(SaleLine_TreeIter)
		# end loop through all items in the SalesEntryGrid_ListStore
		self.SaleTotal_Value.set_label('<b>' + "{0: .2f}".format(self.SaleTotal) + '</b>')
		self.SaleTax_Value.set_label("{0: .2f}".format(self.TaxTotal))


	def EditedSellPrice (self,cell, path, NewText, Data=None):
		if float(NewText)< 0:
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('Prices must be positive numbers'))
			MessageBox.run()
			MessageBox.destroy()
		else:
			self.SaleEntryGrid_ListStore[path][self.Col['SellPrice']] = float(NewText)
			self.SaleEntryGrid_ListStore[path][self.Col['ManualPrice']] = True
			self.RecalculateSaleTotal()

	def EditedQuantity (self, cell, path, NewText, Data=None):
		self.SaleEntryGrid_ListStore[path][self.Col['Quantity']] = float(NewText)
		self.RecalculateSaleTotal()

	def EditedRemarks (self, cell, path, NewText, Data=None):
		self.SaleEntryGrid_ListStore[path][self.Col['Remarks']] = NewText

	def ProcessKeyPress(self, CurrentTreeView, KeyPressed ):
		#What to do when the user presses a key while focus is on the TreeView SaleEntryGrid

		CurrentTreePath, CurrentRow = self.SaleEntryGrid_TreeView.get_cursor()
		if CurrentTreePath != None: #the CurrentTreePath is None if the focus was not on a line in the TreeView
			SaleEntryGrid_TreeIter = self.SaleEntryGrid_ListStore.get_iter(CurrentTreePath)
			Quantity = self.SaleEntryGrid_ListStore.get_value(SaleEntryGrid_TreeIter,self.Col['Quantity'])
			KeyName = gtk.gdk.keyval_name(KeyPressed.keyval)
			print "Key %s (%d) was pressed" % (KeyName, KeyPressed.keyval)
			if KeyPressed.keyval == 65451: # + key pressed
				Quantity = Quantity + 1
				self.SaleEntryGrid_ListStore.set_value(SaleEntryGrid_TreeIter,self.Col['Quantity'],Quantity)
			elif KeyPressed.keyval == 65453: # - key pressed
				Quantity = Quantity - 1
				self.SaleEntryGrid_ListStore.set_value(SaleEntryGrid_TreeIter,self.Col['Quantity'],Quantity)
				if Quantity <=0:
					self.SaleEntryGrid_ListStore.remove(SaleEntryGrid_TreeIter)
			#end case KeyPressed.str
			elif KeyPressed.keyval == 65535: #delete key was pressed
				self.SaleEntryGrid_ListStore.remove(SaleEntryGrid_TreeIter)
				self.ScanCode_Entry.grab_focus()
				#end when pressed Delete
			elif KeyPressed.keyval == 65364: #down key was pressed
				self.SaleEntryGrid_TreeView.set_cursor((CurrentRow+1,),focus_column=None, start_editing=False)
				#end when pressed down
			elif KeyPressed.keyval == 65362: #up key was pressed
				self.SaleEntryGrid_TreeView.set_cursor((CurrentRow-1,),focus_column=None, start_editing=False)
				#end when pressed Up
			elif KeyPressed.keyval == 65289: #TAB key was pressed
				self.ScanCode_Entry.grab_focus()
				#end when TAB key pressed

			self.RecalculateSaleTotal()
			return True

	def SearchCustomers (self, widget, data=None):
		# Populate it with data from the database
		result = self.db.cursor()
		if self.SearchCustomerField=="Customer Code":
			result.execute("SELECT debtorsmaster.debtorno, debtorsmaster.name, branchcode, brname FROM debtorsmaster INNER JOIN custbranch ON debtorsmaster.debtorno=custbranch.debtorno WHERE debtorsmaster.debtorno LIKE ? AND debtorsmaster.currcode=?",('%' + self.SearchCustomer_Entry.get_text() + '%',self.CustomerDetails['currcode']))
		elif self.SearchCustomerField=="Customer Name":
			result.execute("SELECT debtorsmaster.debtorno, debtorsmaster.name, branchcode, brname FROM debtorsmaster INNER JOIN custbranch ON debtorsmaster.debtorno=custbranch.debtorno WHERE debtorsmaster.name LIKE ?",('%' + self.SearchCustomer_Entry.get_text() + '%',))

		#Clear any data in the ListStore
		self.CustomerSearch_ListStore.clear()
		#Now populate it with the new result set
		for Row in result:
			self.CustomerSearch_ListStore.append((Row['debtorno'],Row['name'],Row['branchcode'],Row['brname']))

	def CustomerRadioButtonClicked(self,widget,SearchCriteria):
		self.SearchCustomerField = SearchCriteria
		self.SearchCustomer_Entry.grab_focus()

	def SelectedCustomer (self, treeview, SelectedCustomer_Path, ViewColumn, Data=None):
		#When a customer is selected - double clicked or space on row selected
		SelectedCustomer_Iter = self.CustomerSearch_ListStore.get_iter(SelectedCustomer_Path)
		self.CustomerDetails = self.GetCustomerDetails(self.CustomerSearch_ListStore.get_value(SelectedCustomer_Iter, self.CustomerSearch['DebtorNo']),self.CustomerSearch_ListStore.get_value(SelectedCustomer_Iter, self.CustomerSearch['BranchCode']))
		#Prices could be completely different so need to lookup/apply appropriate discounts again
		#Loop around the current order and update pricing including the new taxes
		SaleLine_TreeIter = self.SaleEntryGrid_ListStore.get_iter_first()
		self.SaleTotal  = 0
		self.TaxTotal =0
		while SaleLine_TreeIter:
			StockID =  self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['SKU'])
			TaxCatID = self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['TaxCatID'])
			Quantity = self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['Quantity'])
			Price = self.GetPrice(StockID, TaxCatID, Quantity)
			self.SaleEntryGrid_ListStore.set_value(SaleLine_TreeIter,self.Col['SellPrice'],Price)
			LineTotal = Price * Quantity
			self.SaleEntryGrid_ListStore.set_value(SaleLine_TreeIter,self.Col['LineTotal'],LineTotal)
			self.SaleTotal  += LineTotal

			print "StockID = " + StockID + " new price = " + str(Price)

			try:
				LineTaxRate = self.TaxRate[TaxCatID]
			except:
				LineTaxRate = 0

			self.TaxTotal += (LineTotal*LineTaxRate/(1+LineTaxRate))
			SaleLine_TreeIter = self.SaleEntryGrid_ListStore.iter_next(SaleLine_TreeIter)

		# end loop through all items in the SalesEntryGrid_ListStore
		self.SaleTotal_Value.set_label('<b>' + "{0: .2f}".format(self.SaleTotal) + '</b>')
		self.SaleTax_Value.set_label("{0: .2f}".format(self.TaxTotal))


		#Set the label in the main window to show the customer
		self.CustomerName_Label.set_label('<b>' + _('Customer') + ': ' + self.CustomerDetails['name']+ '</b>')

		if  self.CustomerDetails['debtorno']!=self.Config['DebtorNo']:
			self.CustomerName_Label.show()
		else:
			self.CustomerName_Label.hide()
		self.CustomerSearch_Dialog.destroy()

	def OpenCustomerSearchDialog (self, widget, data=None):
		self.CustomerSearch_Dialog = gtk.Dialog(_('Customer Search'),self.MainWindow,gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK,gtk.RESPONSE_ACCEPT))

		RowHBox = gtk.HBox(homogeneous=False, spacing=5)
		#Pack the RowHBox into the VerticalBox below the menu
		self.CustomerSearch_Dialog.vbox.pack_start(RowHBox, False, False, 2)
		RowHBox.show()

		Search_Label = gtk.Label(_('Enter Search:'))
		Search_Label.show()
		RowHBox.pack_start(Search_Label,False,False, 2)

		self.SearchCustomerField = 'Customer Code' #set as default to search by Item Code

		self.SearchCustomer_Entry = gtk.Entry()
		self.SearchCustomer_Entry.set_width_chars(20)
		self.SearchCustomer_Entry.set_editable(True)
		self.SearchCustomer_Entry.connect('changed', self.SearchCustomers)
		self.SearchCustomer_Entry.show()
		RowHBox.pack_start(self.SearchCustomer_Entry,False,False, 2)

		RadioBox = gtk.HBox(False, 10)
		RadioBox.set_border_width(10)
		RowHBox.pack_start(RadioBox, True, True, 0)
		RadioBox.show()
		Search_Radio = gtk.RadioButton(None, _('Search Customer _Code'))
		Search_Radio.connect('toggled', self.CustomerRadioButtonClicked, 'Customer Code')
		RadioBox.pack_start(Search_Radio, True, True, 0)
		Search_Radio.set_active(True)
		Search_Radio.show()

		Search_Radio = gtk.RadioButton(Search_Radio, _('Search Customer _Name'))
		Search_Radio.connect('toggled', self.CustomerRadioButtonClicked, 'Customer Name')
		RadioBox.pack_start(Search_Radio, True, True, 0)
		Search_Radio.show()

		separator = gtk.HSeparator()
		RowHBox.pack_start(separator, False, True, 0)
		separator.show()

		self.CustomerSearch = dict()
		self.CustomerSearch['DebtorNo'] = 0
		self.CustomerSearch['Name'] = 1
		self.CustomerSearch['BranchCode'] = 2
		self.CustomerSearch['BranchName'] = 3

		#Define a list store to hold the CustomerSearch
		self.CustomerSearch_ListStore = gtk.ListStore(str,str, str, str)

		#Define a Tree View to display them
		CustomerSearch_TreeView = gtk.TreeView(self.CustomerSearch_ListStore)
		CustomerSearch_TreeView.connect('row_activated',self.SelectedCustomer)
		#Define the columns to hold the data
		DebtorNo_col = gtk.TreeViewColumn(_('Customer Code'))
		Name_col = gtk.TreeViewColumn(_('Customer Name'))
		BranchCode_col = gtk.TreeViewColumn(_('Branch Code'))
		BranchName_col = gtk.TreeViewColumn(_('Branch Name'))
		#Add the colums to the TreeView
		CustomerSearch_TreeView.append_column(DebtorNo_col)
		CustomerSearch_TreeView.append_column(Name_col)
		CustomerSearch_TreeView.append_column(BranchCode_col)
		CustomerSearch_TreeView.append_column(BranchName_col)
		#Define the cells to hold the data
		DebtorNo_cell = gtk.CellRendererText()
		DebtorNo_cell.set_property('width',100)
		DebtorNo_col.pack_start(DebtorNo_cell,True)
		DebtorNo_col.set_attributes(DebtorNo_cell, text=self.CustomerSearch['DebtorNo'])

		Name_cell = gtk.CellRendererText()
		Name_cell.set_property('width',250)
		Name_col.pack_start(Name_cell,True)
		Name_col.set_attributes(Name_cell, text=self.CustomerSearch['Name'])

		BranchCode_cell = gtk.CellRendererText()
		BranchCode_cell.set_property('width',100)
		BranchCode_col.pack_start(BranchCode_cell,True)
		BranchCode_col.set_attributes(BranchCode_cell, text=self.CustomerSearch['BranchCode'])

		BranchName_cell = gtk.CellRendererText()
		BranchName_cell.set_property('width',250)
		BranchName_col.pack_start(BranchName_cell,True)
		BranchName_col.set_attributes(BranchName_cell, text=self.CustomerSearch['BranchName'])

		CustomerSearch_TreeView.show()

		CustomerSearch_ScrolledWindow = gtk.ScrolledWindow(hadjustment=None, vadjustment=None)
		CustomerSearch_ScrolledWindow.set_border_width(10)
		CustomerSearch_ScrolledWindow.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		CustomerSearch_ScrolledWindow.set_size_request(700,400)
		CustomerSearch_ScrolledWindow.add (CustomerSearch_TreeView)
		CustomerSearch_ScrolledWindow.show()

		self.CustomerSearch_Dialog.vbox.pack_start(CustomerSearch_ScrolledWindow, True)

		Response = self.CustomerSearch_Dialog.run()
		if Response == gtk.RESPONSE_ACCEPT:
			CurrentSelection = CustomerSearch_TreeView.get_selection()
			(model, CustomerIter) = CurrentSelection.get_selected()
			if CustomerIter != None:
				self.CustomerDetails = self.GetCustomerDetails(self.CustomerSearch_ListStore.get_value(CustomerIter, self.CustomerSearch['DebtorNo']),self.CustomerSearch_ListStore.get_value(CustomerIter, self.CustomerSearch['BranchCode']))
				self.BranchCode = self.CustomerSearch_ListStore.get_value(CustomerIter, self.CustomerSearch['BranchCode'])
				if  self.CustomerDetails['debtorno']!=self.Config['DebtorNo']:
					self.CustomerName_Label.show()
				else:
					self.CustomerName_Label.hide()

		self.CustomerSearch_Dialog.destroy()

	def OpenLocationStockDialog (self, widget, data=None):

		CurrentSelection = self.SaleEntryGrid_TreeView.get_selection()
		(model, SaleLineIter) = CurrentSelection.get_selected()
		if SaleLineIter == None:
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('There is no item selected in the main POS window. First bring up the item on the sale, select it, then click the inventory location inquiry'))
			MessageBox.run()
			MessageBox.destroy()
			print _('No item selected to inquire on')
		else:
			LocationStock_Dialog = gtk.Dialog(_('Location Inventory Inquiry'),self.MainWindow,gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_NO_SEPARATOR,(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

			LocationStock = dict()
			LocationStock['LocationName'] = 0
			LocationStock['Quantity'] = 1

			#Define a list store to hold the LocationStock
			LocationStock_ListStore = gtk.ListStore(str,float)
			#Get the data using XML-RPC back to the database
			Transport = TimeoutTransport()
			x_server = xmlrpclib.Server(self.Config['webERPXmlRpcServer'],transport=Transport)
			#Do the weberp.xmlrpc_GetStockBalance on the webERP installation
			XMLRPC_Result = x_server.weberp.xmlrpc_GetStockBalance(self.SaleEntryGrid_ListStore.get_value(SaleLineIter,self.Col['SKU']),self.Config['webERPuser'],self.Config['webERPpwd'])

			if XMLRPC_Result[0] != 0:
				MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('The XML-RPC call to retrieve the inventory location inquiry details from webERP was unsucessful. It could be that internet connectivity to the webERP server is down'))
				MessageBox.run()
				MessageBox.destroy()
			else:
				# Populate the ListStore with the data returned from the XML-RPC call
				result = self.db.cursor()
				for InventoryQuantity in XMLRPC_Result[1]:
					result.execute("SELECT locationname FROM locations WHERE loccode=?",(InventoryQuantity['loccode'],))
					for Row in result:
						LocationStock_ListStore.append((Row['locationname'],float(InventoryQuantity['quantity'])))

				#Define a Tree View to display them
				LocationStock_TreeView = gtk.TreeView(LocationStock_ListStore)
				#Define the columns to hold the data
				LocationName_col = gtk.TreeViewColumn(_('Location'))
				Quantity_col = gtk.TreeViewColumn(_('Quantity'))
				#Add the colums to the TreeView
				LocationStock_TreeView.append_column(LocationName_col)
				LocationStock_TreeView.append_column(Quantity_col)
				#Define the cells to hold the data
				LocationName_cell = gtk.CellRendererText()
				LocationName_cell.set_property('width',120)
				LocationName_cell.set_property('mode',gtk.CELL_RENDERER_MODE_INERT)
				LocationName_col.pack_start(LocationName_cell,True)
				LocationName_col.set_attributes(LocationName_cell, text=LocationStock['LocationName'])

				Quantity_cell = gtk.CellRendererText()
				Quantity_cell.set_property('width',130)
				Quantity_cell.set_property('mode',gtk.CELL_RENDERER_MODE_INERT)
				Quantity_col.pack_start(Quantity_cell,True)
				Quantity_col.set_cell_data_func(Quantity_cell, self.FormatDecimalPlaces, LocationStock['Quantity'])

				LocationStock_TreeView.show()

				LocationStock_ScrolledWindow = gtk.ScrolledWindow(hadjustment=None, vadjustment=None)
				LocationStock_ScrolledWindow.set_border_width(10)
				LocationStock_ScrolledWindow.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
				LocationStock_ScrolledWindow.set_size_request(320,200)
				LocationStock_ScrolledWindow.add (LocationStock_TreeView)
				LocationStock_ScrolledWindow.show()

				LocationStock_Dialog.vbox.pack_start(LocationStock_ScrolledWindow, True)

				LocationStock_Dialog.run()
				LocationStock_Dialog.destroy()
		# End of Inventory Location Inquiry Dialog Box

	def PaymentEntered(self, widget, PaymentMethod):
		try:
			Amount = float(self.Payment_Entry.get_text())
		except:
			MessageBox = gtk.MessageDialog(self.EnterPayment_Dialog, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('Only positive numeric values can be entered'))
			MessageBox.run()
			MessageBox.destroy()
			self.Payment_Entry.set_text('0.00')
			print _('Only positive amounts to be entered for payments')
			return 0
		if Amount <0:
			MessageBox = gtk.MessageDialog(self.EnterPayment_Dialog, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('Only positive amounts can be entered for payments'))
			MessageBox.run()
			MessageBox.destroy()
			self.Payment_Entry.set_text("0.00")
			print _('Only positive amounts to be entered for payments')
			return 0
		Payment_TreeIter = self.Payment_ListStore.get_iter_first()
		AddedPayment = False
		self.TotalPayments = 0
		while Payment_TreeIter:
			ThisLinePaymentMethod =  self.Payment_ListStore.get_value(Payment_TreeIter, self.PaymentMethods['ID'])
			if ThisLinePaymentMethod == 9999:
				if (self.SaleTotal - self.TotalPayments - Amount < 0):
					MessageBox = gtk.MessageDialog(self.EnterPayment_Dialog, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _("Cannot charge an account more than is required. If part of the sale is settled by another payment method then only the balance can be charged to the customer\'s account."))
					MessageBox.run()
					MessageBox.destroy()
					self.Payment_Entry.set_text("{0: .2f}".format(self.SaleTotal - self.TotalPayments))
					print _('Cannot charge a customer account more than is required. The sum of other payment methods together with the account charge is greater than the total sale')
					return 0
			print PaymentMethod, ThisLinePaymentMethod
			ThisLinePaymentAmount = float(self.Payment_ListStore.get_value(Payment_TreeIter, self.PaymentMethods['Amount']))
			if int(ThisLinePaymentMethod) == int(PaymentMethod):
				self.Payment_ListStore.set_value(Payment_TreeIter,self.PaymentMethods['Amount'],Amount)
				AddedPayment = True
				self.TotalPayments += Amount
			else:
				self.TotalPayments += ThisLinePaymentAmount
			Payment_TreeIter = self.Payment_ListStore.iter_next(Payment_TreeIter)
		# end loop through all items in the Payment_ListStore
		if AddedPayment==False:
			if PaymentMethod==9999:
				PaymentName = _('Charge Account')
				if (self.SaleTotal - self.TotalPayments - Amount < 0):
					MessageBox = gtk.MessageDialog(self.EnterPayment_Dialog, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _("Cannot charge an account more than is required. If part of the sale is settled by another payment method then only the balance can be charged to the customer\'s account. The amount charged has been changed to") + ' ' + "{0: .2f}".format(self.SaleTotal - self.TotalPayments))
					MessageBox.run()
					MessageBox.destroy()
					self.Payment_Entry.set_text("{0: .2f}".format(self.SaleTotal - self.TotalPayments))
					Amount = (self.SaleTotal - self.TotalPayments)
					print _('Cannot charge a customer account more than is required. The sum of other payment methods together with the account charge is greater than the total sale')
			else:
				result = self.db.cursor()
				result.execute("SELECT paymentname FROM paymentmethods WHERE paymentid=?", (PaymentMethod,))
				Row=result.fetchone()
				PaymentName = Row['paymentname']

			self.Payment_ListStore.append((PaymentMethod, PaymentName, Amount))
			self.TotalPayments += Amount

		self.PaymentTotal_Value.set_label('<b>' + "{0: .2f}".format(self.TotalPayments) + '</b>')
		LeftToPay = self.SaleTotal - self.TotalPayments
		if LeftToPay < 0:
			LeftToPay = 0
		self.LeftToPay_Value.set_label('<b>' + "{0: .2f}".format(LeftToPay) + '</b>')
		self.EnterPayment_Dialog.destroy()

	def EnterPaymentAmount(self, widget, PaymentMethod=None):
		#user clicked a payment method button in the Payment Dialog...
		if PaymentMethod=='Charge_Account':
			PaymentName = _('Account Charge')
			PaymentMethod=9999
		else:
			result = self.db.cursor()
			result.execute("SELECT paymentname FROM paymentmethods WHERE paymentid=?", (PaymentMethod,))
			Row=result.fetchone()
			PaymentName = Row['paymentname']
		self.EnterPayment_Dialog = gtk.Dialog(_('Enter') + ' ' + PaymentName +  ' ' + _('Amount'), self.Payment_Dialog,
			gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT| gtk.DIALOG_NO_SEPARATOR, None)
		Payment_Label = gtk.Label(_('Enter') + ' ' + PaymentName +  ' ' + _('Amount'))
		Payment_Label.show()
		self.EnterPayment_Dialog.vbox.pack_start(Payment_Label,False)
		self.Payment_Entry = gtk.Entry(max=15)
		self.Payment_Entry.editable = True
		self.Payment_Entry.xalign = 1
		self.Payment_Entry.grab_focus()

		#Find out if this payment method is already added to the liststore
		ExistingPaymentMethod = False
		Payment_TreeIter = self.Payment_ListStore.get_iter_first()
		if (int(self.Config['CashPaymentMethodID'])==PaymentMethod):
			#if it is cash then round to the nearest smallest coin
			LeftToPay = self.RoundToSmallestCoin(self.SaleTotal - self.TotalPayments)
		else:
			LeftToPay = self.SaleTotal - self.TotalPayments
		while Payment_TreeIter:
			ThisLinePaymentMethod =  self.Payment_ListStore.get_value(Payment_TreeIter, self.PaymentMethods['ID'])
			ThisLinePaymentAmount = self.Payment_ListStore.get_value(Payment_TreeIter, self.PaymentMethods['Amount'])
			if int(ThisLinePaymentMethod) == int(PaymentMethod):
				#set the entry to the existing amount previously entered
				if float(ThisLinePaymentAmount)==0:
					self.Payment_Entry.set_text("{0: .2f}".format(LeftToPay))
				else:
					self.Payment_Entry.set_text("{0: .2f}".format(ThisLinePaymentAmount))
				ExistingPaymentMethod = True
				break
			Payment_TreeIter = self.Payment_ListStore.iter_next(Payment_TreeIter)
		# end loop through all items in the Payment_ListStore
		if ExistingPaymentMethod == False:
			#Then set the amount to the remaining balance to be paid
			self.Payment_Entry.set_text("{0: .2f}".format(LeftToPay))

		self.Payment_Entry.connect('activate', self.PaymentEntered, PaymentMethod)
		self.Payment_Entry.show()
		self.EnterPayment_Dialog.vbox.pack_start(self.Payment_Entry,False)
		self.EnterPayment_Dialog.run()
		self.EnterPayment_Dialog.destroy()

	def RoundToSmallestCoin (self, Amount):
		NumberofSmallestCoins = Amount / float(self.Config['SmallestCoin'])
		DecimalPart = NumberofSmallestCoins - int(NumberofSmallestCoins)
		if DecimalPart==0:
			return Amount
		elif DecimalPart > 0.51: #rounding up
			return round((Amount+float(self.Config['SmallestCoin'])/2)/float(self.Config['SmallestCoin']))*float(self.Config['SmallestCoin'])
		else:#rounding down
			return round((Amount-float(self.Config['SmallestCoin'])/2)/float(self.Config['SmallestCoin']))*float(self.Config['SmallestCoin'])


	def PaymentComplete(self,widget,data=None):

		OpenCashDrawer = False

		print "Rounded sale total = " + str(self.RoundToSmallestCoin(self.SaleTotal))
		print "Total Payments = " + str(self.TotalPayments)

		if (self.RoundToSmallestCoin(self.SaleTotal) - self.TotalPayments) > 0.009:
			MessageBox = gtk.MessageDialog(self.Payment_Dialog, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('The sale cannot be accepted until sufficient payments have been tendered and entered.'))
			MessageBox.run()
			MessageBox.destroy()
			print _('Insufficient payment entered')
			return
		else:
			#Now process the sale into the database
			#Get the POS transaction number
			result = self.db.cursor()
			result.execute("INSERT INTO transcounter VALUES (NULL)")
			self.LastTransNo = result.lastrowid

			InvoiceParameters = (self.LastTransNo, self.CustomerDetails['debtorno'], self.CustomerDetails['branchcode'], datetime.datetime.now(), self.CustomerDetails['salestype'],  self.SaleTotal - self.TaxTotal, self.TaxTotal)
			result.execute("INSERT INTO debtortrans (id, transno, type, debtorno, branchcode, trandate, tpe, ovamount, ovgst) VALUES (NULL,?,10,?,?,?,?,?,?)", InvoiceParameters)
			DebtorTransID = result.lastrowid

			#Now need to work out the amount for each tax authority - have to run through the lines on the order - or store by tax authority at the time of calculation would be neater.

			#Now to add the stockmoves have to go through the self.SaleGrid_ListStore.iter
			SaleLine_TreeIter = self.SaleEntryGrid_ListStore.get_iter_first()
			while SaleLine_TreeIter:
				StockID =  self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['SKU'])
				#The Gross Price (inclusive of taxes)
				Price =  self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['SellPrice'])
				Quantity = self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['Quantity'])
				TaxCatID = self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['TaxCatID'])
				Remarks = self.SaleEntryGrid_ListStore.get_value(SaleLine_TreeIter, self.Col['Remarks'])
				#We actually want to store the tax exclusive value - we have the total gross from debtortrans ovamount+ ovgst
				#the net price must be sent back to webERP for creating the invoice in webERP
				#also the tax exclusive numbers are more useful for sales analysis
				try:
					LineTaxRate = self.TaxRate[TaxCatID]
				except:
					LineTaxRate =0

				Price /= (1+LineTaxRate)

				StockMovesParameters = (StockID,self.LastTransNo, Price, Quantity, Remarks)
				result.execute("INSERT INTO stockmoves (stkmoveno, stockid, type, transno, price, qty, reference) VALUES (NULL,?,10,?,?,?,?)", StockMovesParameters)

				#And while we are here let's add the stockmovestaxes too ... a bit more tricky
				StockMoveNo = result.lastrowid
				TaxOrder = 0
				AccumTax = 0

				for TaxAuthority, Tax in self.Taxes[TaxCatID].items():
					print 'TaxCatID = ', TaxCatID , '  TaxAuthority = ', TaxAuthority
					if Tax['TaxOnTax']==1:
						self.Taxes[TaxCatID][TaxAuthority]['Amount'] += Tax['Rate']*(Price*Quantity+AccumTax)
					else:
						self.Taxes[TaxCatID][TaxAuthority]['Amount'] += Tax['Rate']*Price*Quantity

					AccumTax += self.Taxes[TaxCatID][TaxAuthority]['Amount']
					StkMoveTaxesParameters = (StockMoveNo,TaxAuthority,Tax['Rate'],Tax['TaxOnTax'],TaxOrder)
					result.execute("INSERT INTO stockmovestaxes (stkmoveno,taxauthid,taxrate,taxontax,taxcalculationorder) VALUES (?,?,?,?,?)",StkMoveTaxesParameters)
					TaxOrder +=1

				SaleLine_TreeIter = self.SaleEntryGrid_ListStore.iter_next(SaleLine_TreeIter)
				# end loop through all items in the SalesEntryGrid_ListStore

			for TaxAuthority, Tax in self.Taxes[TaxCatID].items():
				InvoiceTaxParameters = (DebtorTransID, TaxAuthority, Tax['Amount'])
				result.execute("INSERT INTO debtortranstaxes( debtortransid, taxauthid, taxamount) VALUES (?,?,?)",InvoiceTaxParameters)

			#Now add the debtortrans for the payments made
			#Need to work out if there was any rounding due to coins
			Change = self.RoundToSmallestCoin(self.TotalPayments - self.SaleTotal)
			if Change > 0 :
				ChangeEntered = False
			else:
				ChangeEntered = True

			#PaymentTotal = self.TotalPayments - self.RoundToSmallestCoin(self.TotalPayments - self.SaleTotal)
			Rounding = self.SaleTotal - self.TotalPayments + Change
			if Rounding !=0:
				RoundingEntered = False
			else:
				RoundingEntered = True


			Payment_TreeIter = self.Payment_ListStore.get_iter_first()
			while Payment_TreeIter:
				PaymentMethod =  int(self.Payment_ListStore.get_value(Payment_TreeIter, self.PaymentMethods['ID']))
				PaymentAmount = float(self.Payment_ListStore.get_value(Payment_TreeIter, self.PaymentMethods['Amount']))
				if RoundingEntered == False:
					RoundingAmount = Rounding
					RoundingEntered = True
				else:
					RoundingAmount =0
				if (int(self.Config['CashPaymentMethodID'])==PaymentMethod):
					#Need to take off any change given from the payments made
					PaymentAmount -= Change
					ChangeEntered = True
					PaymentParameters = (self.LastTransNo, self.CustomerDetails['debtorno'], datetime.datetime.now(), PaymentAmount, RoundingAmount, PaymentMethod)
					OpenCashDrawer = True
				else:
					PaymentParameters = (self.LastTransNo, self.CustomerDetails['debtorno'], datetime.datetime.now(), PaymentAmount, RoundingAmount, PaymentMethod)
					NeedCashDrawerParameters = (PaymentMethod,)
					result.execute("SELECT opencashdrawer FROM paymentmethods WHERE paymentid=?",NeedCashDrawerParameters)
					CashDrawerRow = result.fetchone()
					if CashDrawerRow != None:
						if CashDrawerRow['opencashdrawer']==1:
							OpenCashDrawer = True
				# end if its a cash payment method or not
				result.execute("INSERT INTO debtortrans (id, transno, type, debtorno, trandate, ovamount, ovdiscount, paymentmethod) VALUES (NULL,?,12,?,?,?,?,?)", PaymentParameters)
				Payment_TreeIter = self.Payment_ListStore.iter_next(Payment_TreeIter)
			# end loop through all items in the Payment_ListStore

			if ChangeEntered==False:
				PaymentParameters = (self.LastTransNo, self.CustomerDetails['debtorno'], datetime.datetime.now(), -Change, 0, int(self.Config['CashPaymentMethodID']))
				OpenCashDrawer = True
				ChangeEntered = True
				result.execute("INSERT INTO debtortrans (id, transno, type, debtorno, trandate, ovamount, ovdiscount, paymentmethod) VALUES (NULL,?,12,?,?,?,?,?)", PaymentParameters)

			self.db.commit()

			if OpenCashDrawer==True:
				if self.ReceiptPrinter is None:
					MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,_('Cannot connect to a receipt printer. The cash drawer cannot be opened without one being connected to the receipt printer!'))
					MessageBox.run()
					MessageBox.destroy()
				else:
					try:
						self.ReceiptPrinter.cashdraw(2)
					except:
						print _('Could not open cashdrawer')

			if (self.Config['AutoPrintReceipt']=='1' or self.Config['AutoPrintReceipt'].upper()=='YES'):
				self.PrintReceipt(self.LastTransNo)


			#if the Payments are greater than the sale by more than the smallest currency denomination
			if Change > float(self.Config['SmallestCoin']):
			#if the SaleTotal< TotalPayments the show the amount of change in a dialog box
				MessageBox = gtk.MessageDialog(self.Payment_Dialog, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, None )
				MessageBox.set_markup('<b>' + _('Change') + ': ' + "{0: .2f}".format(Change) + '</b>')
				OpenCashDrawer = True
				MessageBox.run()
				MessageBox.destroy()

			#clear the SaleListStore
			self.SaleEntryGrid_ListStore.clear()
			#clear the payments listStore
			self.Payment_ListStore.clear()
			#Set sale total and tax totals to zero
			self.SaleTotal_Value.set_label('<b>0.00</b>')
			self.SaleTax_Value.set_label('0.00')
			self.SaleTotal = 0
			self.TaxTotal = 0
			self.ScanResult_Label.set_text('')
			#if some other customer was selected
			if self.CustomerDetails['debtorno'] != self.Config['DebtorNo']:
				#Get the default customer details again
				self.CustomerDetails = self.GetCustomerDetails(self.Config['DebtorNo'],self.Config['BranchCode'])
				self.CustomerName_Label.hide()

			self.Payment_Dialog.destroy()
			if self.Config['LoginEverySale']=='1':
				#require login for each sale
				self.OpenLoginDialog()
			else:
				self.ScanCode_Entry.grab_focus()

	def PrintLastReceipt(self, widget, data=None):
		if self.LastTransNo ==0:
			result = self.db.cursor()
			result.execute("SELECT max(id), transno FROM debtortrans WHERE type=10 OR type=11")
			TransRow = result.fetchone()
			self.LastTransNo = TransRow['transno']
		self.PrintReceipt(self.LastTransNo)

	def PrintReceipt(self, TransNo):

		if self.ReceiptPrinter is None:
			print _('No receipt printer connected')
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,_('Cannot connect to a receipt printer.'))
			MessageBox.run()
			MessageBox.destroy()
			return

		self.ReceiptPrinter.hw('INIT') #initialise the printer
		self.ReceiptPrinter.set(align='CENTER',type='B') #set bold centred text
		self.ReceiptPrinter.text('INVOICE')
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text(self.Config['POSName'])
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text('Tax #: ' + self.Config['TaxNumber'])
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text(self.UserName_Label.get_text())
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.set(align='LEFT',type='NORMAL') #set normal font left aligned text

		TransHeader = self.db.cursor()
		TransHeader.execute('SELECT transno, name, brname, trandate, ovamount, ovgst, debtortrans.debtorno FROM debtortrans INNER JOIN debtorsmaster ON debtortrans.debtorno=debtorsmaster.debtorno INNER JOIN custbranch ON debtortrans.debtorno=custbranch.debtorno AND debtortrans.branchcode=custbranch.branchcode WHERE transno=? AND type=10',(TransNo,))

		TransRow = TransHeader.fetchone()
		TransDate = datetime.datetime.strptime(TransRow['trandate'], '%Y-%m-%d %H:%M:%S.%f')
		self.ReceiptPrinter.text(_('Date') + ': ')
		if self.Config['DefaultDateFormat']=='d/m/Y':
			self.ReceiptPrinter.text(TransDate.strftime('%d/%m/%Y').ljust(12))
		else:
			self.ReceiptPrinter.text(TransDate.strftime('%m/%d/%Y').ljust(12))

		self.ReceiptPrinter.text(' ' + _('Number') + ': ' + str(TransRow['transno']))
		self.ReceiptPrinter.control('LF')
		if TransRow['debtorno']!=self.Config['DebtorNo']:
			self.ReceiptPrinter.text(_('To') + ': ' + TransRow['name'])
			self.ReceiptPrinter.control('LF')

		self.ReceiptPrinter.control('LF')

		TransLines = self.db.cursor()
		TransLines.execute('SELECT stockmoves.stkmoveno, stockmoves.stockid, description, price, qty, price*qty AS linetotal  FROM stockmoves INNER JOIN stockmaster ON stockmoves.stockid=stockmaster.stockid WHERE transno=? AND type=10',(TransNo,))

		Taxes = self.db.cursor()
		#Trans line header
		self.ReceiptPrinter.set(type='U') #set underline text
		self.ReceiptPrinter.text(' '+_('Quantity') + '   ' + _('Price') + '        ' + _('Total'))
		self.ReceiptPrinter.set(type='NORMAL') #set normal text
		TotalInvoice =0
		TotalBeforeTax=0
		TotalTax =0
		for Line in TransLines:
			self.ReceiptPrinter.control('LF')
			self.ReceiptPrinter.text(_('SKU') + ': ' + Line['stockid'].ljust(20)[:20])
			self.ReceiptPrinter.control('LF')
			self.ReceiptPrinter.text(Line['description'].ljust(32)[:32])
			self.ReceiptPrinter.control('LF')
			if (len(Line['description'])>32):
				self.ReceiptPrinter.text(Line['description'].ljust(32)[32:])
				self.ReceiptPrinter.control('LF')
			#need to figure out effective tax rate now
			Taxes.execute('SELECT taxrate, taxontax FROM stockmovestaxes WHERE stkmoveno=? ORDER BY taxcalculationorder',(Line['stkmoveno'],))
			EffectiveTaxRate =0
			for Tax in Taxes:
				if Tax['taxontax']==1:
					EffectiveTaxRate += (Tax['taxrate']*EffectiveTaxRate)
				EffectiveTaxRate += Tax['taxrate']

			self.ReceiptPrinter.text('{0: .2f}' . format(Line['qty']).rjust(7) + ' @ ' + ('{0: .2f}'.format(Line['price'])).rjust(9) + ' ' + '{0: .2f}'.format(Line['qty']*Line['price']).rjust(11))
			TotalBeforeTax += Line['linetotal']
			TotalInvoice += (Line['linetotal']*(1+EffectiveTaxRate))
			TotalTax += (Line['linetotal']*EffectiveTaxRate)

		#Now print the total
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text('___________'.rjust(32))
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.set(type='BU2') #set bold text
		self.ReceiptPrinter.text(_('Total excl tax') + '  ' + '{0: .2f}'.format(TotalBeforeTax).rjust(15))
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text(_('Tax') + '  ' + '{0: .2f}'.format(TotalTax).rjust(26))
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text('___________'.rjust(32))
                self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text(_('Total') + '  ' + '{0: .2f}'.format(TotalInvoice).rjust(24))
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text('___________'.rjust(32))
                self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.set(type='NORMAL') #set normal text
		Media = self.db.cursor()
		self.ReceiptPrinter.text(_('Paid By:'))
		self.ReceiptPrinter.control('LF')
		Media.execute("SELECT  ovamount, paymentname FROM debtortrans INNER JOIN paymentmethods ON debtortrans.paymentmethod=paymentmethods.paymentid WHERE transno=? AND type=12",(TransNo,))
		TotalMedia = 0
		CountMedia = 0
		for MediaLine in Media:
			self.ReceiptPrinter.text(' ' + MediaLine['paymentname'] + '  ' + '{0: .2f}'.format(MediaLine['ovamount']).rjust(29 - len(MediaLine['paymentname'])))
			self.ReceiptPrinter.control('LF')
			TotalMedia += MediaLine['ovamount']
			CountMedia +=1
		if CountMedia > 1:
			self.ReceiptPrinter.text('___________'.rjust(32))
			self.ReceiptPrinter.control('LF')
			self.ReceiptPrinter.set(type='BU2') #set bold text
			self.ReceiptPrinter.text(' ' + _('Total Media') + '  ' + '{0: .2f}'.format(TotalMedia).rjust(18))
			self.ReceiptPrinter.control('LF')
			self.ReceiptPrinter.text('___________'.rjust(32))
		self.ReceiptPrinter.set(type='NORMAL') #set normal text
		self.ReceiptPrinter.cut() #cut the paper

	def PrintReceipt_old(self, TransNo):

		if self.ReceiptPrinter is None:
			print _('No receipt printer connected')
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,_('Cannot connect to a receipt printer.'))
			MessageBox.run()
			MessageBox.destroy()
			return

		self.ReceiptPrinter.hw('INIT') #initialise the printer
		self.ReceiptPrinter.set(align='CENTER',type='B') #set bold centred text
		self.ReceiptPrinter.text('INVOICE')
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text(self.Config['POSName'])
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text('Tax #: ' + self.Config['TaxNumber'])
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text(self.UserName_Label.get_text())
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.set(align='LEFT',type='NORMAL') #set normal font left aligned text

		TransHeader = self.db.cursor()
		TransHeader.execute('SELECT transno, name, brname, trandate, ovamount, ovgst, debtortrans.debtorno FROM debtortrans INNER JOIN debtorsmaster ON debtortrans.debtorno=debtorsmaster.debtorno INNER JOIN custbranch ON debtortrans.debtorno=custbranch.debtorno AND debtortrans.branchcode=custbranch.branchcode WHERE transno=? AND type=10',(TransNo,))

		TransRow = TransHeader.fetchone()
		TransDate = datetime.datetime.strptime(TransRow['trandate'], '%Y-%m-%d %H:%M:%S.%f')
		self.ReceiptPrinter.text(_('Date') + ': ')
		if self.Config['DefaultDateFormat']=='d/m/Y':
			self.ReceiptPrinter.text(TransDate.strftime('%d/%m/%Y').ljust(12))
		else:
			self.ReceiptPrinter.text(TransDate.strftime('%m/%d/%Y').ljust(12))

		self.ReceiptPrinter.text(' ' + _('Number') + ': ' + str(TransRow['transno']))
		self.ReceiptPrinter.control('LF')
		if TransRow['debtorno']!=self.Config['DebtorNo']:
			self.ReceiptPrinter.text(_('To') + ': ' + TransRow['name'])
			self.ReceiptPrinter.control('LF')

		self.ReceiptPrinter.control('LF')

		TransLines = self.db.cursor()
		TransLines.execute('SELECT stockmoves.stkmoveno, stockmoves.stockid, description, price, qty, price*qty AS linetotal  FROM stockmoves INNER JOIN stockmaster ON stockmoves.stockid=stockmaster.stockid WHERE transno=? AND type=10',(TransNo,))

		Taxes = self.db.cursor()
		#Trans line header
		self.ReceiptPrinter.set(type='U') #set underline text
		self.ReceiptPrinter.text(' '+_('Quantity') + '   ' + _('Price') + '        ' + _('Total'))
		self.ReceiptPrinter.set(type='NORMAL') #set normal text
		TotalInvoice =0
		TotalTax =0
		for Line in TransLines:
			self.ReceiptPrinter.control('LF')
			self.ReceiptPrinter.text(_('SKU') + ': ' + Line['stockid'].ljust(20)[:20])
			self.ReceiptPrinter.control('LF')
			self.ReceiptPrinter.text(Line['description'].ljust(32)[:32])
			self.ReceiptPrinter.control('LF')
			if (len(Line['description'])>32):
				self.ReceiptPrinter.text(Line['description'].ljust(32)[32:])
				self.ReceiptPrinter.control('LF')
			#need to figure out effective tax rate now
			Taxes.execute('SELECT taxrate, taxontax FROM stockmovestaxes WHERE stkmoveno=? ORDER BY taxcalculationorder',(Line['stkmoveno'],))
			EffectiveTaxRate =0
			for Tax in Taxes:
				if Tax['taxontax']==1:
					EffectiveTaxRate += (Tax['taxrate']*EffectiveTaxRate)
				EffectiveTaxRate += Tax['taxrate']

			self.ReceiptPrinter.text('{0: .2f}' . format(Line['qty']).rjust(7) + ' @ ' + ('{0: .2f}'.format(Line['price']*(1+EffectiveTaxRate))).rjust(9) + ' ' + '{0: .2f}'.format(Line['qty']*Line['price']*(1+EffectiveTaxRate)).rjust(11))
			TotalInvoice += (Line['linetotal']*(1+EffectiveTaxRate))
			TotalTax += (Line['linetotal']*EffectiveTaxRate)

		#Now print the total
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text('___________'.rjust(32))
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.set(type='BU2') #set bold text
		self.ReceiptPrinter.text(_('Total') + '  ' + '{0: .2f}'.format(TotalInvoice).rjust(25))
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text(_('Tax included') + '  ' + '{0: .2f}'.format(TotalTax).rjust(18))
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.set(type='NORMAL') #set normal text
		Media = self.db.cursor()
		self.ReceiptPrinter.text(_('Paid By:'))
		self.ReceiptPrinter.control('LF')
		Media.execute("SELECT  ovamount, paymentname FROM debtortrans INNER JOIN paymentmethods ON debtortrans.paymentmethod=paymentmethods.paymentid WHERE transno=? AND type=12",(TransNo,))
		TotalMedia = 0
		CountMedia = 0
		for MediaLine in Media:
			self.ReceiptPrinter.text(' ' + MediaLine['paymentname'] + '  ' + '{0: .2f}'.format(MediaLine['ovamount']).rjust(29 - len(MediaLine['paymentname'])))
			self.ReceiptPrinter.control('LF')
			TotalMedia += MediaLine['ovamount']
			CountMedia +=1
		if CountMedia > 1:
			self.ReceiptPrinter.text('___________'.rjust(32))
			self.ReceiptPrinter.control('LF')
			self.ReceiptPrinter.set(type='BU2') #set bold text
			self.ReceiptPrinter.text(' ' + _('Total Media') + '  ' + '{0: .2f}'.format(TotalMedia).rjust(18))
			self.ReceiptPrinter.control('LF')
			self.ReceiptPrinter.text('___________'.rjust(32))
		self.ReceiptPrinter.set(type='NORMAL') #set normal text
		self.ReceiptPrinter.cut() #cut the paper

	def EndOfDay (self, widget, data=None):
		self.EndOfDay_Dialog = gtk.Dialog(_('End Of Day Summary'),self.MainWindow, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
		result = self.db.cursor()
		result.execute("SELECT type, paymentmethod, sum(ovamount+ovgst) AS totalamount, sum(ovdiscount) AS roundings FROM debtortrans WHERE trandate>=? GROUP BY type, paymentmethod ORDER BY type, paymentmethod", (self.Config['LastEndOfDay'],))

		PaymentMethod = self.db.cursor()
		NoOfPaymentMethods = 0
		NetSales = 0
		TotalTendered = 0

		EndOfDayGrid = gtk.Table(10, 2, False)
		EndOfDayGrid.show()
		self.EndOfDay_Dialog.vbox.pack_start(EndOfDayGrid,False,True,5)
		TotalRoundings = 0

		for Row in result:
			if Row['type']==10:
				InvoicesEntry = gtk.Entry()
				InvoicesEntry.set_text(_('Invoices Total') + ':')
				InvoicesEntry.set_width_chars(23)
				InvoicesEntry.set_editable(False)
				InvoicesEntry.set_can_focus(False)
				InvoicesEntry.set_alignment(1)
				InvoicesTotalEntry=gtk.Entry()
				InvoicesTotalEntry.set_text("{0: .2f}".format(Row['totalamount']))
				InvoicesTotalEntry.set_editable(False)
				InvoicesTotalEntry.set_can_focus(False)
				InvoicesTotalEntry.set_alignment(1)

				EndOfDayGrid.attach(InvoicesEntry, 0, 1, 0, 1)
				EndOfDayGrid.attach(InvoicesTotalEntry, 1, 2, 0, 1)
				InvoicesEntry.show()
				InvoicesTotalEntry.show()
				PaymentsHeadingEntry  = gtk.Entry()
				PaymentsHeadingEntry.set_text(_('Payments Received'))
				PaymentsHeadingEntry.set_editable(False)
				PaymentsHeadingEntry.set_can_focus(False)
				PaymentsHeadingEntry.set_alignment(0.5)

				PaymentsHeadingEntry.show()
				EndOfDayGrid.attach(PaymentsHeadingEntry, 0, 2, 1, 2)
			if Row['type']==12:

				TotalRoundings += Row['roundings']

				if Row['paymentmethod']==9999:
					PytMethod9999Entry = gtk.Entry()
					PytMethod9999Entry.set_text(_('Charged to Accounts') + ':')
					PytMethod9999Entry.set_width_chars(23)
					PytMethod9999Entry.set_editable(False)
					PytMethod9999Entry.set_can_focus(False)
					PytMethod9999Entry.set_alignment(1)
					PytMethod9999AmountEntry = gtk.Entry()
					PytMethod9999AmountEntry.set_text("{0: .2f}".format(float(Row['totalamount'])))
					PytMethod9999AmountEntry.set_editable(False)
					PytMethod9999AmountEntry.set_can_focus(False)
					PytMethod9999AmountEntry.set_alignment(1)
					EndOfDayGrid.attach(PytMethod9999Entry, 0, 1, 2, 3)
					EndOfDayGrid.attach(PytMethod9999AmountEntry, 1, 2, 2, 3)
					PytMethod9999Entry.show()
					PytMethod9999AmountEntry.show()
				else:
					PaymentMethod.execute("SELECT paymentname FROM paymentmethods WHERE paymentid=?",(Row['paymentmethod'], ))
					PaymentMethodRow = PaymentMethod.fetchone()
					if PaymentMethodRow==None:
						continue
					elif NoOfPaymentMethods==0:
						PytMethod0Entry = gtk.Entry()
						PytMethod0Entry.set_text(PaymentMethodRow['paymentname'] + ': ')
						PytMethod0Entry.set_width_chars(23)
						PytMethod0Entry.set_editable(False)
						PytMethod0Entry.set_can_focus(False)
						PytMethod0Entry.set_alignment(1)
						PytMethod0AmountEntry = gtk.Entry()
						PytMethod0AmountEntry.set_text("{0: .2f}".format(float(Row['totalamount'])))
						PytMethod0AmountEntry.set_editable(False)
						PytMethod0AmountEntry.set_can_focus(False)
						PytMethod0AmountEntry.set_alignment(1)
						EndOfDayGrid.attach(PytMethod0Entry, 0, 1, 3, 4)
						EndOfDayGrid.attach(PytMethod0AmountEntry, 1, 2, 3, 4)
						PytMethod0Entry.show()
						PytMethod0AmountEntry.show()
					elif NoOfPaymentMethods==1:
						PytMethod1Entry = gtk.Entry()
						PytMethod1Entry.set_text(PaymentMethodRow['paymentname'] + ': ')
						PytMethod1Entry.set_width_chars(23)
						PytMethod1Entry.set_editable(False)
						PytMethod1Entry.set_can_focus(False)
						PytMethod1Entry.set_alignment(1)
						PytMethod1AmountEntry = gtk.Entry()
						PytMethod1AmountEntry.set_text("{0: .2f}".format(float(Row['totalamount'])))
						PytMethod1AmountEntry.set_editable(False)
						PytMethod1AmountEntry.set_can_focus(False)
						PytMethod1AmountEntry.set_alignment(1)
						EndOfDayGrid.attach(PytMethod1Entry, 0, 1, 4, 5)
						EndOfDayGrid.attach(PytMethod1AmountEntry, 1, 2, 4, 5)
						PytMethod1Entry.show()
						PytMethod1AmountEntry.show()
					elif NoOfPaymentMethods==2:
						PytMethod2Entry = gtk.Entry()
						PytMethod2Entry.set_text(PaymentMethodRow['paymentname'] + ': ')
						PytMethod2Entry.set_width_chars(23)
						PytMethod2Entry.set_editable(False)
						PytMethod2Entry.set_can_focus(False)
						PytMethod2Entry.set_alignment(1)
						PytMethod2AmountEntry = gtk.Entry()
						PytMethod2AmountEntry.set_text("{0: .2f}".format(float(Row['totalamount'])))
						PytMethod2AmountEntry.set_editable(False)
						PytMethod2AmountEntry.set_can_focus(False)
						PytMethod2AmountEntry.set_alignment(1)
						EndOfDayGrid.attach(PytMethod2Entry, 0, 1, 5, 6)
						EndOfDayGrid.attach(PytMethod2AmountEntry, 1, 2, 5, 6)
						PytMethod2Entry.show()
						PytMethod2AmountEntry.show()
					elif NoOfPaymentMethods==3:
						PytMethod3Entry = gtk.Entry()
						PytMethod3Entry.set_text(PaymentMethodRow['paymentname'] + ': ')
						PytMethod3Entry.set_width_chars(23)
						PytMethod3Entry.set_editable(False)
						PytMethod3Entry.set_can_focus(False)
						PytMethod3Entry.set_alignment(1)
						PytMethod3AmountEntry = gtk.Entry()
						PytMethod3AmountEntry.set_text("{0: .2f}".format(float(Row['totalamount'])))
						PytMethod3AmountEntry.set_editable(False)
						PytMethod3AmountEntry.set_can_focus(False)
						PytMethod3AmountEntry.set_alignment(1)
						EndOfDayGrid.attach(PytMethod3Entry, 0, 1, 6, 7)
						EndOfDayGrid.attach(PytMethod3AmountEntry, 1, 2, 6, 7)
						PytMethod3Entry.show()
						PytMethod3AmountEntry.show()
					elif NoOfPaymentMethods==4:
						PytMethod4Entry = gtk.Entry()
						PytMethod4Entry.set_text(PaymentMethodRow['paymentname'] + ': ')
						PytMethod4Entry.set_width_chars(23)
						PytMethod4Entry.set_editable(False)
						PytMethod4Entry.set_can_focus(False)
						PytMethod4Entry.set_alignment(1)
						PytMethod4AmountEntry = gtk.Entry()
						PytMethod4AmountEntry.set_text("{0: .2f}".format(float(Row['totalamount'])))
						PytMethod4AmountEntry.set_editable(False)
						PytMethod4AmountEntry.set_can_focus(False)
						PytMethod4AmountEntry.set_alignment(1)
						EndOfDayGrid.attach(PytMethod4Entry, 0, 1, 7, 8)
						EndOfDayGrid.attach(PytMethod4AmountEntry, 1, 2, 7, 8)
						PytMethod4Entry.show()
						PytMethod4AmountEntry.show()
					elif NoOfPaymentMethods==5:
						PytMethod5Entry = gtk.Entry()
						PytMethod5Entry.set_text(PaymentMethodRow['paymentname'] + ': ')
						PytMethod5Entry.set_width_chars(23)
						PytMethod5Entry.set_editable(False)
						PytMethod5Entry.set_can_focus(False)
						PytMethod5Entry.set_alignment(1)
						PytMethod5AmountEntry = gtk.Entry()
						PytMethod5AmountEntry.set_text("{0: .2f}".format(float(Row['totalamount'])))
						PytMethod5AmountEntry.set_editable(False)
						PytMethod5AmountEntry.set_can_focus(False)
						PytMethod5AmountEntry.set_alignment(1)
						EndOfDayGrid.attach(PytMethod5Entry, 0, 1, 8, 9)
						EndOfDayGrid.attach(PytMethod5AmountEntry, 1, 2, 8, 9)
						PytMethod5Entry.show()
						PytMethod5AmountEntry.show()
					elif NoOfPaymentMethods==6:
						PytMethod6Entry = gtk.Entry()
						PytMethod6Entry.set_text(PaymentMethodRow['paymentname'] + ': ')
						PytMethod6Entry.set_width_chars(23)
						PytMethod6Entry.set_editable(False)
						PytMethod6Entry.set_can_focus(False)
						PytMethod6Entry.set_alignment(1)
						PytMethod6AmountEntry = gtk.Entry()
						PytMethod6AmountEntry.set_text("{0: .2f}".format(float(Row['totalamount'])))
						PytMethod6AmountEntry.set_editable(False)
						PytMethod6AmountEntry.set_can_focus(False)
						PytMethod6AmountEntry.set_alignment(1)
						EndOfDayGrid.attach(PytMethod6Entry, 0, 1, 10, 11)
						EndOfDayGrid.attach(PytMethod5AmountEntry, 1, 2, 10, 11)
						PytMethod6Entry.show()
						PytMethod6AmountEntry.show()
					# end else no payment method 9999
				# end if
				NoOfPaymentMethods+=1
				TotalTendered += Row['totalamount']
			#end if payment type==12 transaction
		#end loop around totals
		RoundingsTotalEntry = gtk.Entry()
		RoundingsTotalEntry.set_text(_('Total Roundings') + ':')
		RoundingsTotalEntry.set_width_chars(23)
		RoundingsTotalEntry.set_editable(False)
		RoundingsTotalEntry.set_can_focus(False)
		RoundingsTotalEntry.set_alignment(1)
		RoundingsTotalAmountEntry = gtk.Entry()
		RoundingsTotalAmountEntry.set_text("{0: .2f}".format(TotalRoundings))
		RoundingsTotalAmountEntry.set_editable(False)
		RoundingsTotalAmountEntry.set_can_focus(False)
		RoundingsTotalAmountEntry.set_alignment(1)

		EndOfDayGrid.attach(RoundingsTotalEntry, 0, 1, 11, 12)
		EndOfDayGrid.attach(RoundingsTotalAmountEntry, 1, 2, 11, 12)
		RoundingsTotalEntry.show()
		RoundingsTotalAmountEntry.show()

		TotalTendered += TotalRoundings

		PytTotalEntry = gtk.Entry()
		PytTotalEntry.set_text(_('Total Payments Tendered') + ':')
		PytTotalEntry.set_width_chars(23)
		PytTotalEntry.set_editable(False)
		PytTotalEntry.set_can_focus(False)
		PytTotalEntry.set_alignment(1)
		PytTotalAmountEntry = gtk.Entry()
		PytTotalAmountEntry.set_text("{0: .2f}".format(TotalTendered))
		PytTotalAmountEntry.set_editable(False)
		PytTotalAmountEntry.set_can_focus(False)
		PytTotalAmountEntry.set_alignment(1)

		EndOfDayGrid.attach(PytTotalEntry, 0, 1, 12, 13)
		EndOfDayGrid.attach(PytTotalAmountEntry, 1, 2, 12, 13)
		PytTotalEntry.show()
		PytTotalAmountEntry.show()
		self.EndOfDay_Dialog.vbox.show()

		PrintSummary_Button = gtk.Button(_('_Print') +"\n" + _('Summary'))
		PrintSummary_Button.show()
		PrintSummary_Button.connect('clicked',self.PrintSummaryEndOfDay)
		self.EndOfDay_Dialog.action_area.pack_start(PrintSummary_Button)
		Print_Button = gtk.Button(_('_Print') + "\n" + _('Detail'))
		Print_Button.show()
		Print_Button.connect('clicked',self.PrintEndOfDay)
		self.EndOfDay_Dialog.action_area.pack_start(Print_Button)
		Reset_Button = gtk.Button(_('_Reset') + "\n" + _('Totals'))
		Reset_Button.show()
		Reset_Button.connect('clicked',self.ResetEndOfDay)
		self.EndOfDay_Dialog.action_area.pack_end(Reset_Button)
		self.EndOfDay_Dialog.show()

	def PrintSummaryEndOfDay (self, widget, data=None):
		if self.ReceiptPrinter is None:
			print _('No receipt printer connected')
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,_('Cannot connect to a receipt printer.'))
			MessageBox.run()
			MessageBox.destroy()
			return

		self.ReceiptPrinter.hw('INIT') #initialise the printer
		self.ReceiptPrinter.set(align='CENTER',type='B') #set bold centred text

		self.ReceiptPrinter.text(_('END OF DAY at') + ' ')
		if self.Config['DefaultDateFormat']=='d/m/Y':
			self.ReceiptPrinter.text(datetime.datetime.now().strftime('%d-%m-%Y %H:%M'))
		else:
			self.ReceiptPrinter.text(datetime.datetime.now().strftime('%m-%d-%Y %H:%M'))

		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text(self.Config['POSName'])
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.set(align='LEFT',type='NORMAL') #set normal font left aligned text

		result = self.db.cursor()
		result.execute("SELECT type, paymentmethod, sum(ovamount+ovgst) AS totalamount, sum(ovdiscount) AS roundings FROM debtortrans WHERE trandate>=? GROUP BY type, paymentmethod ORDER BY type, paymentmethod", (self.Config['LastEndOfDay'],))

		PaymentMethod = self.db.cursor()
		NoOfPaymentMethods = 0
		NetSales = 0
		TotalTendered = 0
		TotalRoundings = 0
		for Row in result:
			if Row['type']==10:
				self.ReceiptPrinter.text(_('Invoices Total').ljust(22) + "{0: .2f}".format(Row['totalamount']).rjust(10))
				self.ReceiptPrinter.control('LF')
				self.ReceiptPrinter.text(_('Payments Received') + ':')
				self.ReceiptPrinter.control('LF')
			if Row['type']==12:
				TotalRoundings += Row['roundings']
				if Row['paymentmethod']==9999:
					self.ReceiptPrinter.text(_('Charged to Accounts').ljust(22) + '{0: .2f}'.format(float(Row['totalamount'])).rjust(10))
					self.ReceiptPrinter.control('LF')
				else:
					PaymentMethod.execute("SELECT paymentname FROM paymentmethods WHERE paymentid=?",(Row['paymentmethod'], ))
					PaymentMethodRow = PaymentMethod.fetchone()
					self.ReceiptPrinter.text(PaymentMethodRow['paymentname'].ljust(22) + "{0: .2f}".format(float(Row['totalamount'])).rjust(10))
					self.ReceiptPrinter.control('LF')
					# end else no payment method 9999
				# end if
				TotalTendered += Row['totalamount']
			#end if payment type==12 transaction
		#end loop around totals
		TotalTendered += TotalRoundings
		self.ReceiptPrinter.text(_('Total Roundings').ljust(22)+ "{0: .2f}".format(TotalRoundings).rjust(10))
		self.ReceiptPrinter.text(_('Total Payments').ljust(22)+ "{0: .2f}".format(TotalTendered).rjust(10))
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.control('LF')

	def PrintEndOfDay (self, widget, data=None):
		#Print Detailed list of transactions since last end of day reset
		if self.ReceiptPrinter is None:
			print _('No receipt printer connected')
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,_('Cannot connect to a receipt printer.'))
			MessageBox.run()
			MessageBox.destroy()
			return

		self.ReceiptPrinter.hw('INIT') #initialise the printer
		self.ReceiptPrinter.set(align='CENTER',type='B') #set bold centred text

		self.ReceiptPrinter.text(_('END OF DAY at') + ' ')
		if self.Config['DefaultDateFormat']=='d/m/Y':
			self.ReceiptPrinter.text(datetime.datetime.now().strftime('%d-%m-%Y %H:%M'))
		else:
			self.ReceiptPrinter.text(datetime.datetime.now().strftime('%m-%d-%Y %H:%M'))

		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.text(self.Config['POSName'])
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.set(align='LEFT',type='NORMAL') #set normal font left aligned text
		result = self.db.cursor()
		result.execute("SELECT type, transno, trandate, debtorno, paymentmethod, sum(ovamount+ovgst) AS totalamount FROM debtortrans WHERE trandate>=? GROUP BY type, transno, paymentmethod ORDER BY type, paymentmethod", (self.Config['LastEndOfDay'],))

		PaymentMethod = self.db.cursor()
		Total = 0
		LastType = 0
		LastPaymentMethod = 0
		for Row in result:
			if (LastType<>Row['type'] and LastType<>0):
				self.ReceiptPrinter.set(type='B') #set bold text
				self.ReceiptPrinter.text(_('Total').ljust(15) + '{0: .2f}'.format(Total).rjust(17))
				Total=0
				self.ReceiptPrinter.control('LF')
				self.ReceiptPrinter.control('LF')
			if Row['type']==10:
				if (LastType<>Row['type']):
					self.ReceiptPrinter.text(_('Invoices') + '/' + _('Returns'))
					self.ReceiptPrinter.control('LF')

				self.ReceiptPrinter.text( str(Row['transno']).ljust(15) + '{0: .2f}'.format(Row['totalamount']).rjust(17))
				self.ReceiptPrinter.control('LF')
				Total+=Row['totalamount']
			if Row['type']==12:
				if Row['paymentmethod']==9999:
					if LastPaymentMethod <> 9999:
						self.ReceiptPrinter.set(type='B') #set bold text
						self.ReceiptPrinter.text(_('Total').ljust(15) + '{0: .2f}'.format(Total).rjust(17))
						Total=0
						self.ReceiptPrinter.control('LF')
						self.ReceiptPrinter.text(_('Charged To Accounts'))
						self.ReceiptPrinter.control('LF')
						self.ReceiptPrinter.set(align='LEFT',type='NORMAL') #set normal font left aligned text

					self.ReceiptPrinter.text(str(Row['debtorno']).ljust(15) + '{0: .2f}'.format(Row['totalamount']).rjust(17))
					self.ReceiptPrinter.control('LF')
					Total+=Row['totalamount']
				else:
					PaymentMethod.execute("SELECT paymentname FROM paymentmethods WHERE paymentid=?",(Row['paymentmethod'], ))
					PaymentMethodRow = PaymentMethod.fetchone()
					if LastPaymentMethod <> Row['paymentmethod'] and LastPaymentMethod<>0:
						self.ReceiptPrinter.set(type='B') #set bold text
						self.ReceiptPrinter.text(_('Total').ljust(15) + '{0: .2f}'.format(Total).rjust(17))
						self.ReceiptPrinter.control('LF')
						self.ReceiptPrinter.control('LF')
						Total=0
					if LastPaymentMethod <> Row['paymentmethod']:
						self.ReceiptPrinter.set(type='B') #set bold text
						self.ReceiptPrinter.text(PaymentMethodRow['paymentname'])
						self.ReceiptPrinter.control('LF')
						self.ReceiptPrinter.set(align='LEFT',type='NORMAL') #set normal font left aligned text

					TransDate = datetime.datetime.strptime(Row['trandate'], '%Y-%m-%d %H:%M:%S.%f')

					if self.Config['DefaultDateFormat']=='d/m/Y':
						self.ReceiptPrinter.text(TransDate.strftime('%d-%m %H:%M').ljust(15))
					else:
						self.ReceiptPrinter.text(TransDate.strftime('%m-%d %H:%M').ljust(15))

					self.ReceiptPrinter.text('{0: .2f}'.format(Row['totalamount']).rjust(17))
					self.ReceiptPrinter.control('LF')
					Total+=Row['totalamount']
					# end else no payment method 9999
				# end if
				LastPaymentMethod = Row['paymentmethod']
			#end if payment type==12 transaction
			LastType = Row['type']
		#end loop around transactions
		if Total !=0:
			#Need to print total for last type/payment method
			self.ReceiptPrinter.set(type='B') #set bold text
			self.ReceiptPrinter.text(_('Total').ljust(15) + '{0: .2f}'.format(Total).rjust(17))
			self.ReceiptPrinter.control('LF')
			self.ReceiptPrinter.control('LF')

		result.execute("SELECT transno, trandate, ovdiscount AS rounding FROM debtortrans WHERE trandate>=? AND type=12 AND ovdiscount<>0 ORDER BY transno", (self.Config['LastEndOfDay'],))
		TotalRoundings =0
		self.ReceiptPrinter.set(type='B') #set bold text
		self.ReceiptPrinter.text(_('Roundings'))
		self.ReceiptPrinter.set(align='LEFT',type='NORMAL') #set normal font left aligned text
		self.ReceiptPrinter.control('LF')
		for Row in result:
			self.ReceiptPrinter.text( str(Row['transno']).ljust(15) + '{0: .2f}'.format(Row['rounding']).rjust(17))
			self.ReceiptPrinter.control('LF')
			TotalRoundings += Row['rounding']

		self.ReceiptPrinter.set(type='B') #set bold text
		self.ReceiptPrinter.text(_('Total Roundings').ljust(15) + '{0: .2f}'.format(TotalRoundings).rjust(17))
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.control('LF')
		Total += TotalRoundings
		self.ReceiptPrinter.set(type='B') #set bold text
		self.ReceiptPrinter.text(_('Total').ljust(15) + '{0: .2f}'.format(Total).rjust(17))
		self.ReceiptPrinter.control('LF')
		self.ReceiptPrinter.control('LF')


	def ResetEndOfDay (self, widget, data=None):
		result = self.db.cursor()
		result.execute("UPDATE config set configvalue=? WHERE configname='LastEndOfDay'",(datetime.datetime.now(),))
		self.db.commit()
		self.Config['LastEndOfDay'] = datetime.datetime.now()
		MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,_('Last End of Day Run Reset to Now'))
		MessageBox.run()
		MessageBox.destroy()

	def OpenPaymentDialog (self, widget, data=None):

		if self.SaleEntryGrid_ListStore.get_iter_first() == None :
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, _('There are no items on the sale so it cannot be completed'))
			MessageBox.run()
			MessageBox.destroy()
			self.ScanCode_Entry.grab_focus()
			return

		self.Payment_Dialog = gtk.Dialog(_('Payment - Complete Sale'),self.MainWindow,
			gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
		#reset the TotalPayments made against the sale to zero
		self.TotalPayments = 0
		#define the dict of PaymentMethods for each column of the TreeView
		self.PaymentMethods = dict()
		self.PaymentMethods['ID'] = 0
		self.PaymentMethods['Description'] = 1
		self.PaymentMethods['Amount'] = 2
		#Define a list store to hold the options
		self.Payment_ListStore = gtk.ListStore(str,str,float)
		# Populate it with data from the database
		result = self.db.cursor()
		result.execute('SELECT paymentid, paymentname FROM paymentmethods')
		MainHBox =gtk.HBox(False,10)
		MainHBox.show()
		SubVBox = gtk.VBox(False,10)
		SubVBox.show()
		MainHBox.pack_start(SubVBox,False,True,5)
		Row0HBox =gtk.HBox(False,10)
		Row0HBox.show()
		SubVBox.pack_start(Row0HBox,False,True,5)
		ButtonCounter=0
		for Row in result:
			#create buttons for each payment method
			if ButtonCounter==0:
				PaytMethod0_Button = gtk.Button(Row['paymentname'])
				PaytMethod0_Button.show()
				PaytMethod0_Button.set_size_request(100,80)
				PaytMethod0_Button.connect('clicked',self.EnterPaymentAmount,Row['paymentid'])
				Row0HBox.pack_start(PaytMethod0_Button,False,True,5)
			elif ButtonCounter==1:
				PaytMethod1_Button = gtk.Button(Row['paymentname'])
				PaytMethod1_Button.show()
				PaytMethod1_Button.set_size_request(100,80)
				PaytMethod1_Button.connect('clicked',self.EnterPaymentAmount,Row['paymentid'])
				Row0HBox.pack_start(PaytMethod1_Button,False,True,5)
			elif ButtonCounter==2:
				PaytMethod2_Button = gtk.Button(Row['paymentname'])
				PaytMethod2_Button.show()
				PaytMethod2_Button.set_size_request(100,80)
				PaytMethod2_Button.connect('clicked',self.EnterPaymentAmount,Row['paymentid'])
				Row1HBox = gtk.HBox(False,10)
				Row1HBox.show()
				SubVBox.pack_start(Row1HBox,False,True,5)
				Row1HBox.pack_start(PaytMethod2_Button,False,True,5)
			elif ButtonCounter==3:
				PaytMethod3_Button = gtk.Button(Row['paymentname'])
				PaytMethod3_Button.show()
				PaytMethod3_Button.set_size_request(100,80)
				PaytMethod3_Button.connect('clicked',self.EnterPaymentAmount,Row['paymentid'])
				Row1HBox.pack_start(PaytMethod3_Button,False,True,5)
			elif ButtonCounter==4:
				PaytMethod4_Button = gtk.Button(Row['paymentname'])
				PaytMethod4_Button.show()
				PaytMethod4_Button.set_size_request(100,80)
				PaytMethod4_Button.connect('clicked',self.EnterPaymentAmount,Row['paymentid'])
				Row2HBox = gtk.HBox(False,10)
				Row2HBox.show()
				SubVBox.pack_start(Row2HBox,False,True,5)
				Row2HBox.pack_start(PaytMethod4_Button,False,True,5)
			elif ButtonCounter==5:
				PaytMethod5_Button = gtk.Button(Row['paymentname'])
				PaytMethod5_Button.show()
				PaytMethod5_Button.set_size_request(100,80)
				PaytMethod5_Button.connect('clicked',self.EnterPaymentAmount,Row['paymentid'])
				Row2HBox.pack_start(PaytMethod5_Button,False,True,5)

			ButtonCounter += 1

		#If it is not the default customer then allow the sale to be charged
		if self.CustomerDetails['debtorno']!=self.Config['DebtorNo']:
			Charge_Button = gtk.Button(_('Charge Account'))
			Charge_Button.show()
			Charge_Button.set_size_request(100,80)
			Charge_Button.connect('clicked',self.EnterPaymentAmount,'Charge_Account')
			Row3HBox = gtk.HBox(False,10)
			Row3HBox.show()
			SubVBox.pack_start(Row3HBox,False,True,5)
			Row3HBox.pack_start(Charge_Button,False,True,5)

		#Define a Tree View to display them
		Payment_TreeView = gtk.TreeView(self.Payment_ListStore)
		#Define the columns to hold the data
		PaymentName_col = gtk.TreeViewColumn(_('Payment Method'))
		Amount_col = gtk.TreeViewColumn(_('Amount'))
		#Add the colums to the TreeView
		Payment_TreeView.append_column(PaymentName_col)
		Payment_TreeView.append_column(Amount_col)
		#Define the cells to hold the data
		PaymentName_cell = gtk.CellRendererText()
		PaymentName_cell.set_property('width',100)
		PaymentName_col.pack_start(PaymentName_cell,True)
		PaymentName_col.set_attributes(PaymentName_cell, text=self.PaymentMethods['Description'])

		Amount_cell = gtk.CellRendererText()
		Amount_cell.set_property('width',100)
		Amount_cell.set_property('mode',gtk.CELL_RENDERER_MODE_INERT)
		Amount_cell.set_property('xalign', 1)
		Amount_col.pack_start(Amount_cell,True)
		Amount_col.set_cell_data_func(Amount_cell, self.FormatDecimalPlaces, self.PaymentMethods['Amount'])

		Payment_TreeView.show()

		Payment_ScrolledWindow = gtk.ScrolledWindow(hadjustment=None, vadjustment=None)
		Payment_ScrolledWindow.set_border_width(10)
		Payment_ScrolledWindow.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		Payment_ScrolledWindow.set_size_request(300,200)
		Payment_ScrolledWindow.add (Payment_TreeView)
		Payment_ScrolledWindow.show()

		RightVBox = gtk.VBox(False,0)
		RightVBox.show()
		RightVBox.pack_start(Payment_ScrolledWindow, False,True,5)

		PaymentTotal_Label = gtk.Label('<b>' + _('Total Payment') + ':</b>')
		PaymentTotal_Label.set_use_markup(True)
		PaymentTotal_Label.show()

		PaymentTotal_HBox = gtk.HBox(homogeneous=False, spacing=0)
		PaymentTotal_HBox.pack_start(PaymentTotal_Label,False,True,0)
		PaymentTotal_HBox.show()

		self.PaymentTotal_Value = gtk.Label('<b>0.00</b>')
		self.PaymentTotal_Value.set_use_markup(True)
		self.PaymentTotal_Value.set_justify(gtk.JUSTIFY_RIGHT)
		self.PaymentTotal_Value.show()
		PaymentTotal_HBox.pack_end(self.PaymentTotal_Value,False,True,0)

		PaymentTotalFrame = gtk.Frame(label=None)
		PaymentTotalFrame.add(PaymentTotal_HBox)
		PaymentTotalFrame.set_shadow_type(gtk.SHADOW_IN)
		PaymentTotalFrame.show()

		RightVBox.pack_start(PaymentTotalFrame,False,True,0)

		LeftToPay_Label = gtk.Label('<b>' + _('Left To Pay') + ':</b>')
		LeftToPay_Label.set_use_markup(True)
		LeftToPay_Label.show()

		LeftToPay_HBox = gtk.HBox(homogeneous=False, spacing=0)
		LeftToPay_HBox.pack_start(LeftToPay_Label,False,True,0)
		LeftToPay_HBox.show()

		self.LeftToPay_Value = gtk.Label('<b>' + "{0: .2f}".format(self.SaleTotal) + '</b>')
		self.LeftToPay_Value.set_use_markup(True)
		self.LeftToPay_Value.set_justify(gtk.JUSTIFY_RIGHT)
		self.LeftToPay_Value.show()
		LeftToPay_HBox.pack_end(self.LeftToPay_Value,False,True, 0)

		LeftToPayFrame = gtk.Frame(label=None)
		LeftToPayFrame.add(LeftToPay_HBox)
		LeftToPayFrame.set_shadow_type(gtk.SHADOW_IN)
		LeftToPayFrame.show()

		RightVBox.pack_start(LeftToPayFrame,False,True,0)

		MainHBox.pack_start(RightVBox,False)
		self.Payment_Dialog.vbox.pack_start(MainHBox, False)
		PaymentComplete_Button = gtk.Button(_('OK'))
		PaymentComplete_Button.show()
		PaymentComplete_Button.connect('clicked',self.PaymentComplete)
		self.Payment_Dialog.action_area.pack_end(PaymentComplete_Button)
		self.Payment_Dialog.show()

	def OpenOptionsDialog (self, widget, data=None):

		Options_Dialog = gtk.Dialog(_('Configuration Options'),self.MainWindow,gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

		self.Options = dict()
		self.Options['ConfigName'] = 0
		self.Options['ConfigValue'] = 1
		#Define a list store to hold the options
		self.Options_ListStore = gtk.ListStore(str,str)
		# Populate it with data from the database
		result = self.db.cursor()
		result.execute("SELECT configname, configvalue FROM config WHERE configname<>'LastEndOfDay'")
		for Row in result:
			#DefaultShipper and DefaultDateFormat are the webERP values and come down with data upload
			if (Row['configname']!='DefaultShipper' and Row['configname']!='DefaultDateFormat'):
				self.Options_ListStore.append((Row['configname'],Row['configvalue']))

		#Define a Tree View to display them
		Options_TreeView = gtk.TreeView(self.Options_ListStore)
		#Define the columns to hold the data
		ConfigName_col = gtk.TreeViewColumn(_('Option Name'))
		ConfigValue_col = gtk.TreeViewColumn(_('Option Value'))
		#Add the colums to the TreeView
		Options_TreeView.append_column(ConfigName_col)
		Options_TreeView.append_column(ConfigValue_col)
		#Define the cells to hold the data
		ConfigName_cell = gtk.CellRendererText()
		ConfigName_cell.set_property('width',300)
		ConfigName_col.pack_start(ConfigName_cell,True)
		ConfigName_col.set_attributes(ConfigName_cell, text=self.Options['ConfigName'])

		ConfigValue_cell = gtk.CellRendererText()
		ConfigValue_cell.set_property('width',450)
		ConfigValue_cell.set_property('editable',True)
		ConfigValue_cell.connect('edited', self.EditedConfigValue, self.Options_ListStore )
		ConfigValue_col.pack_start(ConfigValue_cell,True)
		ConfigValue_col.set_attributes(ConfigValue_cell, text=self.Options['ConfigValue'])

		Options_TreeView.show()

		Options_ScrolledWindow = gtk.ScrolledWindow(hadjustment=None, vadjustment=None)
		Options_ScrolledWindow.set_border_width(10)
		Options_ScrolledWindow.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		Options_ScrolledWindow.set_size_request(850,720)
		Options_ScrolledWindow.add (Options_TreeView)
		Options_ScrolledWindow.show()

		Options_Dialog.vbox.pack_start(Options_ScrolledWindow, True)

		Options_Dialog.run()
		Options_Dialog.destroy()


	def EditedConfigValue (self,cell,path,NewText,Data=None):
		result = self.db.cursor()
		print NewText
		#if self.Options_ListStore[path][self.Options['ConfigName']] == 'DebtorNo':
		#	ValidEntry = self.GetCustomerDetails(NewText,self.Config['BranchCode'])
		if self.Options_ListStore[path][self.Options['ConfigName']] == 'LoginEverySale':
			if NewText =='1':
				ValidEntry = True
			elif NewText =='0':
				ValidEntry = True
			else:
				MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('The value of LoginEverySale should be either 1 or 0. 1 meaning that a login is required for every sale and 0 for logins to be persistent.'))
				MessageBox.run()
				MessageBox.destroy()
				print _('Login Every Sale is not either 1 or 0')
		elif self.Options_ListStore[path][self.Options['ConfigName']] == 'SmallestCoin':
			SmallestCoin = 0
			try:
				SmallestCoin = float(NewText)

			except:
				MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _("The value of the currency's smallest coin") + ' ' + NewText +  ' ' + _('is not a numeric value'))
				MessageBox.run()
				MessageBox.destroy()
				print _('The smallest coin value is not numeric!!')
			if SmallestCoin > 0:
					ValidEntry = True
		else:
			ValidEntry = True

		if (ValidEntry==True):
			#Change the value of the config variable in the list_store
			self.Options_ListStore[path][self.Options['ConfigValue']] = NewText
			#update the database
			result = self.db.cursor()
			result.execute("UPDATE config SET configvalue=? WHERE configname=?",(NewText,self.Options_ListStore[path][self.Options['ConfigName']]))
			self.db.commit()
			#Change the Config dict value to the new value
			self.Config[self.Options_ListStore[path][self.Options['ConfigName']]] = NewText


	def OpenPaymentMethodBankAccountsDialog (self, widget, data=None):

		MethodAccounts_Dialog = gtk.Dialog(_('Payment Methods - Bank Accounts'),self.MainWindow,gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

		self.MethodAccounts = dict()
		self.MethodAccounts['PaymentMethodID'] = 0
		self.MethodAccounts['PaymentMethodName'] = 1
		self.MethodAccounts['BankAccount'] = 2
		#Define a list store to hold the bank account payment method mapping
		self.MethodAccounts_ListStore = gtk.ListStore(int,str,str)
		# Populate it with data from the database
		result = self.db.cursor()
		result.execute("SELECT paymentid, paymentname, bankaccount FROM paymentmethods LEFT JOIN bankpaymentmethod ON paymentmethods.paymentid=bankpaymentmethod.methodid")
		for Row in result:
			self.MethodAccounts_ListStore.append((int(Row['paymentid']),str(Row['paymentname']),str(Row['bankaccount'])))

		#Define a Tree View to display them
		MethodAccounts_TreeView = gtk.TreeView(self.MethodAccounts_ListStore)
		#Define the columns to hold the data
		PaymentMethodName_col = gtk.TreeViewColumn(_('Method Name'))
		BankAccount_col = gtk.TreeViewColumn(_('Bank Account'))
		#Add the colums to the TreeView
		MethodAccounts_TreeView.append_column(PaymentMethodName_col)
		MethodAccounts_TreeView.append_column(BankAccount_col)
		#Define the cells to hold the data
		PaymentMethodName_cell = gtk.CellRendererText()
		PaymentMethodName_cell.set_property('width',150)
		PaymentMethodName_col.pack_start(PaymentMethodName_cell,True)
		PaymentMethodName_col.set_attributes(PaymentMethodName_cell, text=self.MethodAccounts['PaymentMethodName'])

		BankAccount_cell = gtk.CellRendererText()
		BankAccount_cell.set_property('width',100)
		BankAccount_cell.set_property('editable',True)
		BankAccount_cell.connect('edited', self.EditedMethodAccounts, self.MethodAccounts_ListStore )
		BankAccount_col.pack_start(BankAccount_cell,True)
		BankAccount_col.set_attributes(BankAccount_cell, text=self.MethodAccounts['BankAccount'])

		MethodAccounts_TreeView.show()

		MethodAccounts_ScrolledWindow = gtk.ScrolledWindow(hadjustment=None, vadjustment=None)
		MethodAccounts_ScrolledWindow.set_border_width(10)
		MethodAccounts_ScrolledWindow.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		MethodAccounts_ScrolledWindow.set_size_request(300,250)
		MethodAccounts_ScrolledWindow.add (MethodAccounts_TreeView)
		MethodAccounts_ScrolledWindow.show()

		MethodAccounts_Dialog.vbox.pack_start(MethodAccounts_ScrolledWindow, True)

		MethodAccounts_Dialog.run()
		MethodAccounts_Dialog.destroy()

	def EditedMethodAccounts (self,cell,path,NewText,Data=None):
		result = self.db.cursor()
		self.MethodAccounts_ListStore[path][self.MethodAccounts['BankAccount']] = int(NewText)
		result.execute("SELECT methodid FROM bankpaymentmethod WHERE methodid=?",(self.MethodAccounts_ListStore[path][self.MethodAccounts['PaymentMethodID']],))
		i=0
		for Row in result:
			i+=1

		if (i==0):
			result.execute("INSERT INTO bankpaymentmethod (methodid,bankaccount) VALUES (?,?)",(self.MethodAccounts_ListStore[path][self.MethodAccounts['PaymentMethodID']],int(NewText)))
		else:
			result.execute("UPDATE bankpaymentmethod SET bankaccount=? WHERE methodid=?",(int(NewText),self.MethodAccounts_ListStore[path][self.MethodAccounts['PaymentMethodID']]))
		self.MethodAccounts[self.MethodAccounts_ListStore[path][self.MethodAccounts['BankAccount']]] =int(NewText)


	def FormatDecimalPlaces(self, Column, Renderer, Model, Iter, ColNumber):
		#Called from a treeview column with data_func to format the data to show 2 dp
		#NumberToFormat = Model.get_value(Iter, ColNumber)
		Renderer.set_property('text', "{0: .2f}".format(Model.get_value(Iter, ColNumber)))

	def AboutDialogBox (self, widget, data=None):
		About = gtk.AboutDialog()
		About.set_program_name('Counter-Logic for webERP')
		About.set_version(Version)
		About.set_copyright("(c) Logic Works Ltd and Python esc/pos (c) Manuel F Martinez")
		About.set_comments(_('A Point of Sale Application that Integrates with webERP'))
		About.set_website('http://www.logicworks.co.nz')
		About.set_logo(gtk.gdk.pixbuf_new_from_file(InstallDirectory + "/images/logo.png"))
		About.run()
		About.destroy()


	def PasswordEntered(self, widget, Data=None):
		#Check username and password match
		result=self.db.cursor()
		CheckUserPasswordParameters = (self.User_Entry.get_text(), self.Pwd_Entry.get_text())
		result.execute("SELECT realname, admin FROM users WHERE username=? AND password=?", CheckUserPasswordParameters)
		i=0
		for row in result:
			i+=1
			if row['admin']==1:
				self.AdministratorLoggedIn = True
			else:
				self.AdministratorLoggedIn = False

		if i==1: #The user was found in the database
			OperatorNameText = _('Operator') + ': ' + row['realname']
			self.UserName_Label.set_label('<b>' + OperatorNameText + '</b>')
			self.LoginDialogBox.destroy()
			self.LoggedIn = True
			self.ScanCode_Entry.grab_focus()
		else:
			self.LoginError_Label.set_text(_('Incorrect Username/Password entered. Please retry'))
			self.LoggedIn = False
			self.User_Entry.set_text('')
			self.Pwd_Entry.set_text('')
			self.User_Entry.grab_focus()

	def UserEntered(self, widget, data=None):
		#clear password and move focus to password
		self.Pwd_Entry.set_text('')
		self.Pwd_Entry.grab_focus()

	def UserChanged(self, widget, data=None):
		#see if the length of the username has reached the length required by config
		Lengths = self.Config['UserPasswordLength'].split(',')
		LengthOfUserName = int(Lengths[0])
		if len(self.User_Entry.get_text()) == LengthOfUserName :
			self.UserEntered(widget)

	def PasswordChanged(self, widget, data=None):
		#see if the length of the password has reached the length required by config
		Lengths = self.Config['UserPasswordLength'].split(',')
		LengthOfPassword = int(Lengths[1])
		if len(self.User_Entry.get_text()) == LengthOfPassword :
			self.PasswordEntered(widget)

	def OpenLoginDialog(self):
		#------------ Define Login Dialog Box --------------
		self.LoginDialogBox=gtk.Dialog(_('Login'),self.MainWindow,gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_NO_SEPARATOR,(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		self.LoginDialogBox.connect('delete_event', self.destroy)

		User_Label = gtk.Label(_('User Name') + ':')
		User_Label.show()

		Lengths = self.Config['UserPasswordLength'].split(',')
		LengthOfUserName = int(Lengths[0])
		LengthOfPassword = int(Lengths[1])

		self.User_Entry = gtk.Entry()
		self.User_Entry.set_width_chars(LengthOfUserName)
		self.User_Entry.editable = True
		self.User_Entry.grab_focus()
		self.User_Entry.connect('changed', self.UserChanged)
		self.User_Entry.connect('activate', self.UserEntered)
		self.User_Entry.show()

		User_HBox = gtk.HBox(True,10)
		User_HBox.show()
		User_HBox.pack_start(User_Label,True,True)
		User_HBox.pack_start(self.User_Entry,True,True)

		Pwd_Label = gtk.Label(_('Password') + ':')
		Pwd_Label.show()

		self.Pwd_Entry = gtk.Entry()
		self.Pwd_Entry.set_width_chars(LengthOfPassword)
		self.Pwd_Entry.set_visibility(False) #the text is hidden since its a password!
		self.Pwd_Entry.editable = True
		self.Pwd_Entry.connect('activate',self.PasswordEntered)
		self.Pwd_Entry.connect('changed',self.PasswordChanged)
		self.Pwd_Entry.show()

		Pwd_HBox = gtk.HBox(True,10)
		Pwd_HBox.show()
		Pwd_HBox.pack_start(Pwd_Label,True,True)
		Pwd_HBox.pack_start(self.Pwd_Entry,True,True)

		self.LoginError_Label = gtk.Label('')
		self.LoginError_Label.show()

		self.LoginDialogBox.vbox.pack_start(User_HBox,True,True)
		self.LoginDialogBox.vbox.pack_start(Pwd_HBox,True,True)
		self.LoginDialogBox.vbox.pack_start(self.LoginError_Label,True,True)

		Response = self.LoginDialogBox.run()
		if Response == gtk.RESPONSE_ACCEPT:
			self.PasswordEntered(self.LoginDialogBox)

	def UserSelected(self, widget, data=None):
		if widget.get_active_text()==_('New User'):
			self.UserID_Entry.set_text('')
			self.UserName_Entry.set_text('')
			self.Passwd_Entry.set_text('')
			self.PasswdChk_Entry.set_text('')
			self.AdminUser_CheckBox.set_active(False)
			self.UserID_Entry.grab_focus()
			self.Delete_Button.hide()
			self.Add_Button.show()
			self.Update_Button.hide()
		else:
			result = self.db.cursor()
			result.execute("SELECT username, password, realname, admin FROM users WHERE username=?",(widget.get_active_text(),))
			UserRow = result.fetchone()
			self.UserID_Entry.set_text(UserRow['username'])
			self.UserID_Entry.editable = False
			self.UserName_Entry.set_text(UserRow['realname'])
			self.Passwd_Entry.set_text(UserRow['password'])
			self.PasswdChk_Entry.set_text(UserRow['password'])
			self.UserName_Entry.grab_focus()
			print 'admin field = ' + str(UserRow['admin'])

			if UserRow['admin']=='true':
				self.AdminUser_CheckBox.set_active(True)
			else:
				self.AdminUser_CheckBox.set_active(False)
			self.Delete_Button.show()
			self.Add_Button.hide()
			self.Update_Button.show()


	def UserMaintenanceDialog(self,widget, data=None):

		if self.AdministratorLoggedIn == False:
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('User maintenance is only available to system administrators'))
			MessageBox.run()
			MessageBox.destroy()
			print _('User maintenance only available to admins')
			return

		self.UserMaintDialogBox=gtk.Dialog(_('User Maintenance'),self.MainWindow,gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_NO_SEPARATOR)

		Lengths = self.Config['UserPasswordLength'].split(',')
		LengthOfUserName = int(Lengths[0])
		LengthOfPassword = int(Lengths[1])

		SelectUser_Label = gtk.Label(_('Select User') + ':')
		SelectUser_Label.show()

		self.User_ComboBox = gtk.combo_box_new_text()
		self.User_ComboBox.connect("changed", self.UserSelected)
		self.User_ComboBox.append_text('New User')
		self.User_ComboBox.show()

		SelectUser_HBox = gtk.HBox(True,10)
		SelectUser_HBox.show()
		SelectUser_HBox.pack_start(SelectUser_Label,True,True)
		SelectUser_HBox.pack_start(self.User_ComboBox,True,True)

		result = self.db.cursor()
		result.execute("SELECT username, password, realname, admin FROM users")

		for Row in result:
			self.User_ComboBox.append_text(str(Row['username']))

		UserID_Label = gtk.Label(_('User ID') + ':')
		UserID_Label.show()

		self.UserID_Entry = gtk.Entry()
		self.UserID_Entry.set_width_chars(LengthOfUserName)
		self.UserID_Entry.editable = True
		self.UserID_Entry.grab_focus()
		self.UserID_Entry.show()

		User_HBox = gtk.HBox(True,10)
		User_HBox.show()
		User_HBox.pack_start(UserID_Label,True,True)
		User_HBox.pack_start(self.UserID_Entry,True,True)

		UserName_Label = gtk.Label(_('User Name') + ':')
		UserName_Label.show()

		self.UserName_Entry = gtk.Entry()
		self.UserName_Entry.set_width_chars(LengthOfUserName)
		self.UserName_Entry.editable = True
		self.UserName_Entry.show()

		UserName_HBox = gtk.HBox(True,10)
		UserName_HBox.show()
		UserName_HBox.pack_start(UserName_Label,True,True)
		UserName_HBox.pack_start(self.UserName_Entry,True,True)

		Passwd_Label = gtk.Label(_('Password') + ':')
		Passwd_Label.show()

		self.Passwd_Entry = gtk.Entry()
		self.Passwd_Entry.set_width_chars(LengthOfPassword)
		self.Passwd_Entry.set_visibility(False) #the text is hidden since its a password!
		self.Passwd_Entry.editable = True
		self.Passwd_Entry.show()

		Pwd_HBox = gtk.HBox(True,10)
		Pwd_HBox.show()
		Pwd_HBox.pack_start(Passwd_Label,True,True)
		Pwd_HBox.pack_start(self.Passwd_Entry,True,True)

		PasswdChk_Label = gtk.Label(_('Check Password') + ':')
		PasswdChk_Label.show()

		self.PasswdChk_Entry = gtk.Entry()
		self.PasswdChk_Entry.set_width_chars(LengthOfPassword)
		self.PasswdChk_Entry.set_visibility(False) #the text is hidden since its a password!
		self.PasswdChk_Entry.editable = True
		self.PasswdChk_Entry.show()

		PasswdChk_HBox = gtk.HBox(True,10)
		PasswdChk_HBox.show()
		PasswdChk_HBox.pack_start(PasswdChk_Label,True,True)
		PasswdChk_HBox.pack_start(self.PasswdChk_Entry,True,True)

		AdminUser_Label = gtk.Label(_('Administrator') + ':')
		AdminUser_Label.show()
		self.AdminUser_CheckBox = gtk.CheckButton('Sys Admin User')
		self.AdminUser_CheckBox.show()

		AdminUser_HBox = gtk.HBox(True,10)
		AdminUser_HBox.show()
		AdminUser_HBox.pack_start(AdminUser_Label,True,True)
		AdminUser_HBox.pack_start(self.AdminUser_CheckBox,True,True)

		self.Delete_Button = gtk.Button(stock=gtk.STOCK_DELETE)
		self.Delete_Button.connect('clicked',self.DeleteUser)
		self.Add_Button = gtk.Button(stock=gtk.STOCK_ADD)
		self.Add_Button.connect('clicked',self.AddUser)
		self.Update_Button=gtk.Button(stock=gtk.STOCK_SAVE)
		self.Update_Button.connect('clicked',self.UpdateUser)

		Buttons_HBox = gtk.HBox(True,10)
		Buttons_HBox.show()
		Buttons_HBox.pack_start(self.Delete_Button,True,True)
		Buttons_HBox.pack_start(self.Add_Button,True,True)
		Buttons_HBox.pack_start(self.Update_Button,True,True)

		self.UserMaintDialogBox.vbox.pack_start(SelectUser_HBox,True,True)
		self.UserMaintDialogBox.vbox.pack_start(User_HBox,True,True)
		self.UserMaintDialogBox.vbox.pack_start(UserName_HBox,True,True)
		self.UserMaintDialogBox.vbox.pack_start(Pwd_HBox,True,True)
		self.UserMaintDialogBox.vbox.pack_start(PasswdChk_HBox,True,True)
		self.UserMaintDialogBox.vbox.pack_start(AdminUser_HBox,True,True)
		self.UserMaintDialogBox.vbox.pack_start(Buttons_HBox,True,True)

		Response = self.UserMaintDialogBox.run()
		self.UserMainDialogBox.destroy()

	def UpdateUser(self, widget, data=None):
		if self.Passwd_Entry.get_text() != self.PasswdChk_Entry.get_text():
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('The password and check password entries do not match - this user record has not been updated. Please try again'))
			MessageBox.run()
			MessageBox.destroy()
			print _('Password check does not match - no update to user')
			return
		if self.AdminUser_CheckBox.get_active() == True:
			AdminUser = 1
		else:
			AdminUser = 0

		result = self.db.cursor()
		result.execute("UPDATE users SET password=?, realname=?, admin=? WHERE username=?",(self.Passwd_Entry.get_text(),self.UserName_Entry.get_text(),AdminUser,self.UserID_Entry.get_text()))
		self.db.commit()
		MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('User record updated'))
		MessageBox.run()
		MessageBox.destroy()
		print _('User Name') + ' ' + str(self.UserName_Entry.get_text()) + ' ' + _('updated')
		self.UserID_Entry.set_text('')
		self.UserName_Entry.set_text('')
		self.Passwd_Entry.set_text('')
		self.PasswdChk_Entry.set_text('')
		self.AdminUser_CheckBox.set_active(False)
		self.UserID_Entry.grab_focus()
		self.Delete_Button.hide()
		self.Add_Button.show()
		self.Update_Button.hide()

	def DeleteUser (self, widget, data=None):
		result = self.db.cursor()
		result.execute("DELETE FROM users WHERE username=?",(self.UserID_Entry.get_text(), ))
		self.db.commit()
		MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('User record deleted'))
		MessageBox.run()
		MessageBox.destroy()
		print _('User Name') + ' ' + str(self.UserName_Entry.get_text()) + ' ' + _('deleted')
		self.UserID_Entry.set_text('')
		self.UserName_Entry.set_text('')
		self.Passwd_Entry.set_text('')
		self.PasswdChk_Entry.set_text('')
		self.AdminUser_CheckBox.set_active(False)
		self.UserID_Entry.grab_focus()
		self.Delete_Button.hide()
		self.Add_Button.show()
		self.Update_Button.hide()

	def AddUser (self, widget, data=None):
		if self.Passwd_Entry.get_text() != self.PasswdChk_Entry.get_text():
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('The password and check password entries do not match - this user record has not been added. Please try again'))
			MessageBox.run()
			MessageBox.destroy()
			print _('Password check does not match - no new user added')
			return

		if self.AdminUser_CheckBox.get_active() == True:
			AdminUser = 1
		else:
			AdminUser = 0
		result = self.db.cursor()
		result.execute("INSERT INTO users (username, password, realname, admin) VALUES(?,?,?,?)",(self.UserID_Entry.get_text(),self.Passwd_Entry.get_text(),self.UserName_Entry.get_text(),AdminUser))
		self.db.commit()

		self.User_ComboBox.append_text(self.UserID_Entry.get_text())

		MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, _('User added'))
		MessageBox.run()
		MessageBox.destroy()
		print _('User Name') + ' ' + str(self.UserName_Entry.get_text()) + ' ' + _('added')
		self.UserID_Entry.set_text('')
		self.UserName_Entry.set_text('')
		self.Passwd_Entry.set_text('')
		self.PasswdChk_Entry.set_text('')
		self.AdminUser_CheckBox.set_active(False)
		self.UserID_Entry.grab_focus()
		self.Delete_Button.hide()
		self.Add_Button.show()
		self.Update_Button.hide()


	def UpdatewebERPData(self, widget, data=None):
		if os.name =='posix':
			if getattr(sys, 'frozen', False):
				os.system('"' + InstallDirectory + '/Linker" full')
			else:
				os.system('"' + InstallDirectory + '/Linker.py" full')
		else:
                        if getattr(sys, 'frozen', False):
                                subprocess.call(InstallDirectory + '/Linker.exe full')
                        else:
                                subprocess.call('python ' + InstallDirectory + '/Linker.py full')


	def SendTowebERP(self, widget, data=None):
		if os.name =='posix':
			print 'Path is: ' + InstallDirectory + '/Linker.py send'
			if getattr(sys, 'frozen', False):
				os.system('"' + InstallDirectory + '/Linker" send')
			else:
				os.system('"' + InstallDirectory + '/Linker.py" send')
		else:
			subprocess.call(InstallDirectory + '\Linker.exe send')

	def ResetData(self,data=None):
		print ("Running the reset transactional data function")
		MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, _('Delete all local transactional data? NB:You will lose any transactions that have not been sent back to the webERP server.'))
		if MessageBox.run() == gtk.RESPONSE_OK:
			MessageBox.run()
			#if MessageBox.get_widget_for_response(response_id=gtk.RESPONSE_YES):
			result = self.db.cursor()
			result.execute("DELETE FROM debtortrans")
			result.execute("DELETE FROM debtortranstaxes")
			result.execute("DELETE FROM stockmoves")
			result.execute("DELETE FROM stockmovestaxes")
			self.db.commit()
			print("data purged!!")
		MessageBox.destroy()

	def GetConfig(self):
		#Get the configuration parameters
		result = self.db.cursor()
		try:
			result.execute("SELECT configname, configvalue FROM config")
		except sqlite3.OperationalError:
			print _('Database not present at') + ' ' + InstallDirectory + ' ' + _('there is an error in your installation of CounterLogic POS')
			sys.exit(0)


		#Create an associative array of parameters configname:confvalue
		Config=dict()
		for row in result:
			Config[row['configname']] = row['configvalue']
		return Config



#---------------------------------------------------------------------------------------------------------
#-------------------- Start of Constructor for CounterLogic Class Definition -----------------------------
#---------------------------------------------------------------------------------------------------------

	def __init__(self):

		#connect to the SQLite database named CounterLogic.sqlite
		print InstallDirectory + '/data/CounterLogic.sqlite'
		self.db = sqlite3.connect(InstallDirectory + '/data/CounterLogic.sqlite')
		self.db.row_factory = sqlite3.Row
		# db database handle for sqlite3 calls

		#Get the configuration of this install and store in a dict Config
		self.Config=self.GetConfig()
		#for configname, ConfValue in Config.iteritems():
		#	print configname, ConfValue

		self.MainWindow=gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.MainWindow.set_position(gtk.WIN_POS_CENTER)
		self.MainWindow.set_title('Counter Logic POS: ' + self.Config['POSName'])
		self.MainWindow.set_default_size(1000,700)
		self.MainWindow.set_name('CounterLogicPOS')

		self.MainWindow.connect('delete_event', self.delete_event)
		self.MainWindow.connect('destroy', lambda x: gtk.main_quit())

		self.MainWindow.set_icon_from_file(InstallDirectory + "/images/logo.png") #the application icon

		GtkSettings = gtk.settings_get_default()
		GtkSettings.set_long_property ("gtk-button-images", 1, "");


		self.LoggedIn=0 #insist on user logging in
		self.AdministratorLoggedIn = False
		self.TaxRate = None
		self.SaleTotal =0
		self.TaxTotal=0
		self.TotalPayments=0
		self.LastTransNo=0

		# File Menu
		FileMenu = gtk.Menu()

		UserMenuItem = gtk.MenuItem(_('_User Maintenance'))
		UserMenuItem.connect('activate',self.UserMaintenanceDialog)
		FileMenu.append(UserMenuItem)
		UserMenuItem.show()

		QuitMenuItem = gtk.MenuItem(_('_Quit'))
		QuitMenuItem.connect('activate',self.destroy,None)
		FileMenu.append(QuitMenuItem)
		QuitMenuItem.show()
		#End File Menu

		SearchMenu = gtk.Menu()

		SearchItemsMenuItem = gtk.MenuItem(_('Search _Items'))
		SearchItemsMenuItem.connect('activate',self.OpenSearchItemsDialog, None)
		SearchMenu.append(SearchItemsMenuItem)
		SearchItemsMenuItem.show()

		SearchCustomersMenuItem = gtk.MenuItem(_('Search _Customers'))
		SearchCustomersMenuItem.connect('activate',self.OpenCustomerSearchDialog,None)
		SearchMenu.append(SearchCustomersMenuItem)
		SearchCustomersMenuItem.show()

		StockMenuItem = gtk.MenuItem(_('See _Location Stock'))
		StockMenuItem.connect('activate',self.OpenLocationStockDialog,None)
		SearchMenu.append(StockMenuItem)
		StockMenuItem.show()

		ToolsMenu = gtk.Menu()

		PrintLastTransMenuItem = gtk.MenuItem(_('_Print Last Receipt'))
		PrintLastTransMenuItem.connect('activate',self.PrintLastReceipt,None)
		ToolsMenu.append(PrintLastTransMenuItem)
		PrintLastTransMenuItem.show()

		EndOfDayMenuItem = gtk.MenuItem(_('_End Of Day'))
		EndOfDayMenuItem.connect('activate',self.EndOfDay,None)
		ToolsMenu.append(EndOfDayMenuItem)
		EndOfDayMenuItem.show()

		webERPUpdateMenuItem = gtk.MenuItem(_('_Download Data'))
		webERPUpdateMenuItem.connect('activate',self.UpdatewebERPData,None)
		ToolsMenu.append(webERPUpdateMenuItem)
		webERPUpdateMenuItem.show()

		SendTowebERPMenuItem = gtk.MenuItem(_('_Upload Transactions'))
		SendTowebERPMenuItem.connect('activate',self.SendTowebERP,None)
		ToolsMenu.append(SendTowebERPMenuItem)
		SendTowebERPMenuItem.show()

		OptionsMenuItem = gtk.MenuItem(_('_Options'))
		OptionsMenuItem.connect("activate",self.OpenOptionsDialog,None)
		ToolsMenu.append(OptionsMenuItem)
		OptionsMenuItem.show()

		MethodMappingMenuItem = gtk.MenuItem(_('_Payment Method Mapping'))
		MethodMappingMenuItem.connect("activate",self.OpenPaymentMethodBankAccountsDialog,None)
		ToolsMenu.append(MethodMappingMenuItem)
		MethodMappingMenuItem.show()

		ResetMenuItem = gtk.MenuItem(_('_Reset Local Data'))
		ResetMenuItem.connect("activate", self.ResetData)
		ToolsMenu.append(ResetMenuItem)
		ResetMenuItem.show()

		#About Menu with Image
		AboutMenu = gtk.Menu()
		AboutMenuItem = gtk.MenuItem(_('_About'))
		AboutMenuItem.connect("activate",self.AboutDialogBox,None)
		AboutMenu.append(AboutMenuItem)
		AboutMenuItem.show()
		#End About Menu

		#Now hang the two menus off a menu bar
		bar = gtk.MenuBar()
		bar.show()
		#Create Menu Items for the bar to allocate the submenus to
		File_Menu_Item = gtk.MenuItem(_('_File'))
		File_Menu_Item.show()
		File_Menu_Item.set_submenu(FileMenu)

		Search_Menu_Item = gtk.MenuItem(_('_Search'))
		Search_Menu_Item.show()
		Search_Menu_Item.set_submenu(SearchMenu)

		Tools_Menu_Item = gtk.MenuItem(_('_Tools'))
		Tools_Menu_Item.show()
		Tools_Menu_Item.set_submenu(ToolsMenu)

		About_Menu_Item = gtk.MenuItem(_('_About'))
		About_Menu_Item.show()
		About_Menu_Item.set_submenu(AboutMenu)
		#Add these Menu Items to the bar
		bar.append(File_Menu_Item)
		bar.append(Search_Menu_Item)
		bar.append(Tools_Menu_Item)
		bar.append(About_Menu_Item)
		#----------- END MENU ---------------------
		#Create the Main Vertical Box for all controls to be added to - this is the top left box
		VerticalBox = gtk.VBox(homogeneous=False, spacing=5)
		#Put the Menu Bar as the first control on the window - at the top
		VerticalBox.pack_start(bar, False, True, 0)
		self.MainWindow.add(VerticalBox)
		VerticalBox.show()
		#Create A Main Horizontal Box for adding controls to the window
		MainHBox = gtk.HBox(homogeneous=False, spacing=5)
		MainHBox.show()
		VerticalBox.pack_start(MainHBox,False, True, 0)

		#Create a Left V Box for the left part of the display
		LeftVBox = gtk.VBox(homogeneous=False, spacing=5)
		LeftVBox.show()
		MainHBox.pack_start(LeftVBox, False, False, 2)

		#Create the first row HBox - that will be packed into the VBox
		Row1HBox = gtk.HBox(homogeneous=False, spacing=5)
		#Pack the Row1HBox into the Main H Box below the menu
		LeftVBox.pack_start(Row1HBox, False, False, 2)
		Row1HBox.show()

		ScanCode_Label = gtk.Label('<b>' + _('Scan Code') + ':</b>')
		ScanCode_Label.set_use_markup(True)
		ScanCode_Label.show()
		Row1HBox.pack_start(ScanCode_Label,False,False, 2)

		self.ScanCode_Entry = gtk.Entry()
		self.ScanCode_Entry.set_width_chars(20)
		self.ScanCode_Entry.set_editable(True)
		self.ScanCode_Entry.connect('activate', self.PopulateScannedItem)
		self.ScanCode_Entry.show()
		Row1HBox.pack_start(self.ScanCode_Entry,False,False, 2)

		self.ScanResult_Label = gtk.Label('')
		self.ScanResult_Label.show()
		Row1HBox.pack_start(self.ScanResult_Label,False,False, 2)



		#Create a dict called Col to hold the Column numbers of the ListStore in
		#Would not mean anything if used numbers in the code and it would be difficult to understand
		self.Col =dict()
		self.Col['SKU']=0
		self.Col['Description']=1
		self.Col['SellPrice']=2
		self.Col['Quantity']=3
		self.Col['LineTotal']=4
		self.Col['DecimalPlaces']=5
		self.Col['TaxCatID']=6
		self.Col['ManualPrice']=7
		self.Col['DiscountCategory']=8
		self.Col['Remarks']=9

		self.SaleEntryGrid_ListStore = gtk.ListStore(str, str, float, float, float, int, int, bool, str, str)
		self.SaleEntryGrid_TreeView = gtk.TreeView(self.SaleEntryGrid_ListStore)
		treeselection = self.SaleEntryGrid_TreeView.get_selection()
		treeselection.set_mode(gtk.SELECTION_SINGLE)
		self.SaleEntryGrid_TreeView.set_enable_search(True)
		self.SaleEntryGrid_TreeView.set_search_column(0)
		self.SaleEntryGrid_TreeView.set_headers_clickable(False)
		self.SaleEntryGrid_TreeView.show()
		#Ensure the event mask is set to enable capture of key presses on the tree view
		self.SaleEntryGrid_TreeView.add_events(gtk.gdk.KEY_PRESS_MASK)
		#Create the link to the ProcessKeyPress function
		self.SaleEntryGrid_TreeView.connect('key_press_event', self.ProcessKeyPress)

		#Create the columns
		SaleEntryGrid_SKU_Col = gtk.TreeViewColumn(_('SKU'))
		SaleEntryGrid_Description_Col = gtk.TreeViewColumn(_('Description'))
		SaleEntryGrid_Remarks_Col = gtk.TreeViewColumn(_('Remarks'))
		SaleEntryGrid_SellPrice_Col = gtk.TreeViewColumn(_('Sell Price'))
		SaleEntryGrid_Quantity_Col = gtk.TreeViewColumn(_('Quantity'))
		SaleEntryGrid_LineTotal_Col = gtk.TreeViewColumn(_('Line Total'))

		#Add the columns to the TreeView
		self.SaleEntryGrid_TreeView.append_column(SaleEntryGrid_SKU_Col)
		self.SaleEntryGrid_TreeView.append_column(SaleEntryGrid_Description_Col)
		self.SaleEntryGrid_TreeView.append_column(SaleEntryGrid_Remarks_Col)
		self.SaleEntryGrid_TreeView.append_column(SaleEntryGrid_SellPrice_Col)
		self.SaleEntryGrid_TreeView.append_column(SaleEntryGrid_Quantity_Col)
		self.SaleEntryGrid_TreeView.append_column(SaleEntryGrid_LineTotal_Col)

		#Create the cell renderers
		Code_CellRend = gtk.CellRendererText()
		Code_CellRend.set_property('width', 150)
		Code_CellRend.set_property('xalign', 0)


		ItemDescription_CellRend = gtk.CellRendererText()
		ItemDescription_CellRend.set_property('width', 330)

		Remarks_CellRend = gtk.CellRendererText()
		Remarks_CellRend.set_property('width', 120)
		Remarks_CellRend.set_property('editable', True)
		Remarks_CellRend.connect('edited', self.EditedRemarks, self.SaleEntryGrid_ListStore )
		#Remarks_CellRend.set_property('xalign', 1)

		SellPrice_CellRend = gtk.CellRendererText()
		SellPrice_CellRend.set_property('width', 80)
		SellPrice_CellRend.set_property('editable', True)
		SellPrice_CellRend.connect('edited', self.EditedSellPrice, self.SaleEntryGrid_ListStore )
		SellPrice_CellRend.set_property('xalign', 1)

		Quantity_CellRend = gtk.CellRendererText()
		Quantity_CellRend.set_property('width', 80)
		Quantity_CellRend.set_property('editable', True)
		Quantity_CellRend.connect('edited',self.EditedQuantity, self.SaleEntryGrid_ListStore )
		Quantity_CellRend.set_property('xalign', 1)

		LineTotal_CellRend = gtk.CellRendererText()
		LineTotal_CellRend.set_property('width', 90)
		LineTotal_CellRend.set_property('xalign', 1)

		#Assign cell renderers for each column
		SaleEntryGrid_SKU_Col.pack_start(Code_CellRend,True)
		SaleEntryGrid_SKU_Col.set_attributes(Code_CellRend, text=self.Col['SKU'])

		SaleEntryGrid_Description_Col.pack_start(ItemDescription_CellRend,True)
		SaleEntryGrid_Description_Col.set_attributes(ItemDescription_CellRend, text=self.Col['Description'])

		SaleEntryGrid_Remarks_Col.pack_start(Remarks_CellRend,True)
		SaleEntryGrid_Remarks_Col.set_attributes(Remarks_CellRend, text=self.Col['Remarks'])

		SaleEntryGrid_SellPrice_Col.pack_start(SellPrice_CellRend,True)
		SaleEntryGrid_Quantity_Col.pack_end(Quantity_CellRend,True)
		SaleEntryGrid_LineTotal_Col.pack_end(LineTotal_CellRend,True)

		#Add Column Rendering functions as needed for SellPrice_Col Quantity_Col and LineTotal_Col
		SaleEntryGrid_SellPrice_Col.set_cell_data_func(SellPrice_CellRend, self.FormatDecimalPlaces, self.Col['SellPrice'])
		SaleEntryGrid_Quantity_Col.set_cell_data_func(Quantity_CellRend, self.FormatDecimalPlaces, self.Col['Quantity'])
		SaleEntryGrid_LineTotal_Col.set_cell_data_func(LineTotal_CellRend, self.FormatDecimalPlaces, self.Col['LineTotal'])

		#Create a scrolled window to put the SalesEntryGrid_TreeView in
		SaleEntryGrid_ScrolledWindow = gtk.ScrolledWindow(hadjustment=None, vadjustment=None)
		SaleEntryGrid_ScrolledWindow.set_border_width(10)
		SaleEntryGrid_ScrolledWindow.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		SaleEntryGrid_ScrolledWindow.set_size_request(920,620)
		SaleEntryGrid_ScrolledWindow.add (self.SaleEntryGrid_TreeView)
		SaleEntryGrid_ScrolledWindow.show()

		#Create a Row5 HBox to pack SalesEntryGrid_ScrolledWindow into
		Row5HBox = gtk.HBox(homogeneous=False, spacing=5)
		Row5HBox.pack_start(SaleEntryGrid_ScrolledWindow,False,False,2)
		Row5HBox.show()

		#Now pack the Row 5 HBox into the VerticalBox
		LeftVBox.pack_start(Row5HBox, False, False, 2)

		#Create and New Row10 HBox to put footer controls into
		Row10HBox = gtk.HBox(homogeneous=False, spacing=5)
		Row10HBox.show()

		SaleTotal_Label = gtk.Label('<b>' + _('Sale Total') + ':</b>')
		SaleTotal_Label.set_use_markup(True)
		SaleTotal_Label.show()

		SaleTotal_HBox = gtk.HBox(homogeneous=False, spacing=5)
		SaleTotal_HBox.pack_start(SaleTotal_Label,False,False, 2)
		SaleTotal_HBox.show()

		self.SaleTotal_Value = gtk.Label('<b>0.00</b>')
		self.SaleTotal_Value.set_use_markup(True)
		self.SaleTotal_Value.set_justify(gtk.JUSTIFY_RIGHT)
		self.SaleTotal_Value.show()
		SaleTotal_HBox.pack_start(self.SaleTotal_Value,False, False, 2)

		SaleTotalFrame = gtk.Frame(label=None)
		SaleTotalFrame.add(SaleTotal_HBox)
		SaleTotalFrame.set_shadow_type(gtk.SHADOW_IN)
		SaleTotalFrame.show()

		Row10HBox.pack_end(SaleTotalFrame,False,False, 2)

		self.SaleTax_Value = gtk.Label('0.00')
		self.SaleTax_Value.set_use_markup(True)
		self.SaleTax_Value.set_justify(gtk.JUSTIFY_RIGHT)
		self.SaleTax_Value.show()

		Row10HBox.pack_end(self.SaleTax_Value,False,False, 2)

		SaleTax_Label = gtk.Label(_('Total Tax'))
		SaleTax_Label.set_use_markup(True)
		SaleTax_Label.show()
		Row10HBox.pack_end(SaleTax_Label,False,False, 2)

		self.UserName_Label = gtk.Label('')
		self.UserName_Label.set_use_markup(True)
		self.UserName_Label.xalign = 0
		self.UserName_Label.show()
		Row10HBox.pack_start(self.UserName_Label,False,False, 2)
		#CustomerDetail for the default POS customer (no customer account selected yet)
		self.CustomerName_Label = gtk.Label('')
		self.CustomerName_Label.set_use_markup(True)
		Row10HBox.pack_start(self.CustomerName_Label,False,False, 2)
		#Pack the Row10HBox into the VerticalBox below the POS items scrolled window
		LeftVBox.pack_start(Row10HBox, False, False, 2)


		self.CustomerDetails = self.GetCustomerDetails(self.Config['DebtorNo'],self.Config['BranchCode'])
		self.DefaultSalesType = self.CustomerDetails['salestype']

		#Create a Left V Box for the left part of the display
		RightVBox = gtk.VBox(homogeneous=False, spacing=5)
		RightVBox.show()

		SearchItems_button = gtk.Button()
		SearchItems_button.set_size_request(180,100)
		SearchItems_button.show()
		SearchItems_button.connect('clicked', self.OpenSearchItemsDialog)
		IconImage = gtk.Image()
		IconImage.set_from_file("./images/scan_add_items.png")
		IconImage.show()
		SearchItems_button.set_image(IconImage)
		SearchItems_button.set_label(_('Search')  + "\n" + _('Items'))
		SearchItems_style = SearchItems_button.style
		SearchItems_style.font_desc

		Exit_button = gtk.Button(_('E_xit'), stock=gtk.STOCK_QUIT)
		Exit_button.set_size_request(150,100)
		Exit_button.show()
		Exit_button.connect('clicked', self.destroy)


		ButtonRow1 =gtk.HBox(homogeneous=False, spacing=5)
		ButtonRow1.pack_start(SearchItems_button,False,False, 2)
		ButtonRow1.pack_start(Exit_button,False,False, 2)
		ButtonRow1.show()

		RightVBox.pack_start(ButtonRow1,False, False, 2)

		SearchCustomers_button = gtk.Button()
		SearchCustomers_button.show()
		SearchCustomers_button.set_size_request(180,100)
		SearchCustomers_button.connect('clicked', self.OpenCustomerSearchDialog)
		IconImage1 = gtk.Image()
		IconImage1.set_from_file("./images/search_customers.png")
		IconImage1.show()
		SearchCustomers_button.set_image(IconImage1)
		SearchCustomers_button.set_label(_('Search') + "\n" + _('_Customers'))

		InventoryQuantity_button = gtk.Button()
		InventoryQuantity_button.show()
		InventoryQuantity_button.set_size_request(150,100)
		InventoryQuantity_button.connect('clicked',self.OpenLocationStockDialog)
		IconImage2 = gtk.Image()
		IconImage2.set_from_file("./images/location_inquiry.png")
		IconImage2.show()
		InventoryQuantity_button.set_image(IconImage2)
		InventoryQuantity_button.set_label(_('_Location') + "\n" + _('Inquiry'))

		ButtonRow2 =gtk.HBox(homogeneous=False, spacing=5)
		ButtonRow2.pack_start(SearchCustomers_button,False,False, 2)
		ButtonRow2.pack_start(InventoryQuantity_button,False,False, 2)
		ButtonRow2.show()

		RightVBox.pack_start(ButtonRow2,False, False, 2)

		EnterPayment_button = gtk.Button()
		EnterPayment_button.show()
		EnterPayment_button.set_size_request(150,100)
		EnterPayment_button.connect('clicked',self.OpenPaymentDialog)
		IconImage3 = gtk.Image()
		IconImage3.set_from_file("./images/pay_complete.png")
		IconImage3.show()
		EnterPayment_button.set_image(IconImage3)
		EnterPayment_button.set_label(_('_Payment and') + "\n" + _('Complete Sale'))

		RightVBox.pack_start(EnterPayment_button,False, False, 2)

		ButtonRow3 =gtk.HBox(homogeneous=False, spacing=5)
		PrintLastReceipt_button = gtk.Button()
		PrintLastReceipt_button.show()
		PrintLastReceipt_button.set_size_request(250,100)
		PrintLastReceipt_button.connect('clicked',self.PrintLastReceipt)
		IconImage4 = gtk.Image()
		IconImage4.set_from_file("./images/print_receipt.png")
		IconImage4.show()
		PrintLastReceipt_button.set_image(IconImage4)
		PrintLastReceipt_button.set_label(_('Print Last') +"\n" + _('_Receipt'))

		ButtonRow3.pack_start(PrintLastReceipt_button,False,False, 2)
		ButtonRow3.show()
		RightVBox.pack_start(ButtonRow3,False, False, 2)

		MainHBox.pack_start(RightVBox, False, False, 2)

		self.MainWindow.show()
		self.ReceiptPrinter = None
		print int(self.Config['ReceiptPrinterVendorID'],16)
		print int(self.Config['ReceiptPrinterProductID'],16)
		try:
		# escpos Receipt Printer Initialisation

			self.ReceiptPrinter = Escpos(int(self.Config['ReceiptPrinterVendorID'],16),int(self.Config['ReceiptPrinterProductID'],16))

		except:
			MessageBox = gtk.MessageDialog(self.MainWindow, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,_('Cannot connect to a receipt printer. The cash drawer cannot be opened without a receipt printer with attached cash drawer!') )
			MessageBox.run()
			MessageBox.destroy()

		self.OpenLoginDialog() # force user to login before anything can happen


#--------------------------- End of Main POS window ----------------------------



#-------------------- Receipt Printing Code Escpos as modified ---------------

class Escpos:
	""" ESC/POS Printer object """
	handle    = None
	device    = None

	def __init__(self, PrinterVendorID, PrinterProductID) :
		#PrinterVendorID and PrinterProductID must be integer or hex values
		# find our device
		if os.name =='posix':
			#specify the backend as libusb-1.0 other backends don't work
			print "we are doing the linux stuff to choose usblib-1.0"
			backend = usb.backend.libusb1.get_backend(find_library=lambda x: "/usr/lib/libusb-1.0.so")
			self.device = usb.core.find(idVendor=PrinterVendorID, idProduct=PrinterProductID, backend=backend)
		else:
			self.device = usb.core.find(idVendor=PrinterVendorID, idProduct=PrinterProductID)

		# was it found?
		if self.device is None:
			print _("Cable isn't plugged in")
			raise ValueError(_('Device not found'))

		if os.name =='posix':#only detatch kernel driver in *nix not supported in Windows
			if self.device.is_kernel_driver_active(0) is True:
				self.device.detach_kernel_driver(0)

		# set the active configuration. With no arguments, the first
		# configuration will be the active one
		self.device.set_configuration()

		#get the configuration
		cfg = self.device.get_active_configuration()
		#get the first interface/alternate interface
		interface_number = cfg[(0,0)].bInterfaceNumber
		alternate_setting = usb.control.get_interface(self.device, interface_number)
		intf = usb.util.find_descriptor(
			cfg, bInterfaceNumber = interface_number,
			bAlternateSetting = alternate_setting
		)

		self.handle = usb.util.find_descriptor(
			intf,
			# match the first OUT endpoint
			custom_match = \
			lambda e: \
				usb.util.endpoint_direction(e.bEndpointAddress) == \
				usb.util.ENDPOINT_OUT
		)
		assert self.handle is not None


	def _raw(self, msg):
		""" Print any of the commands above, or clear text """
		self.handle.write(msg)

	def text(self, txt):
		""" Print alpha-numeric text """
		if txt:
			self._raw(txt)
		else:
			raise TextError()


	def set(self, align='left', font='a', type='normal', width=1, height=1):
		""" Set text properties """
		# Align
		if align.upper() == "CENTER":
			self._raw('\x1b\x61\x01') # justify centre
		elif align.upper() == "RIGHT":
			self._raw('\x1b\x61\x02')  # justify right
		elif align.upper() == "LEFT":
			self._raw('\x1b\x61\x00')  # justify left
		# Font
		if font.upper() == "B":
			self._raw('\x1b\x4d\x01') # Font B
		else:  # DEFAULT FONT: A
			self._raw('\x1b\x4d\x00') # Font A
		# Type
		if type.upper() == "B":
			self._raw('\x1b\x45\x01') # Bold On
			self._raw('\x1b\x2d\x00') # Underline Off
		elif type.upper() == "U":
			self._raw('\x1b\x45\x00')
			self._raw('\x1b\x2d\x01') # Underline On
		elif type.upper() == "U2":
			self._raw('\x1b\x45\x00') # Bold off
			self._raw('\x1b\x2d\x02') # double underline on
		elif type.upper() == "BU":
			self._raw('\x1b\x45\x01') # Bold On
			self._raw('\x1b\x2d\x01') # Underline On
		elif type.upper() == "BU2":
			self._raw('\x1b\x45\x01')  # Bold On
			self._raw('\x1b\x2d\x02')  # double underline on
		elif type.upper == "NORMAL":
			self._raw('\x1b\x45\x00')  # Bold Off
			self._raw('\x1b\x2d\x00') # underline off
		# Width
		if width == 2 and height != 2:
			self._raw('\x1b\x21\x00') # Normal text
			self._raw('\x1b\x21\x20') # 2 x width
		elif height == 2 and width != 2:
			self._raw('\x1b\x21\x00')  # Normal text
			self._raw('\x1b\x21\x10')  # 2 x height
		elif height == 2 and width == 2:
			self._raw('\x1b\x21\x20') # 2 x width
			self._raw('\x1b\x21\x10') # 2 x height
		else: # DEFAULT SIZE: NORMAL
			self._raw('\x1b\x21\x00') # Normal text


	def cut(self, mode=''):
		""" Cut paper """
		# Fix the size between last line and cut
		# TODO: handle this with a line feed
		self._raw("\n\n\n\n\n\n")
		if mode.upper() == "PART":
			self._raw('\x1d\x56\x01')
		else: # DEFAULT MODE: FULL CUT
			self._raw('\x1d\x56\x00')


	def cashdraw(self, pin):
		""" Send pulse to kick the cash drawer """
		if pin == 2:
			self._raw('\x1b\x70\x00') # Sends a pulse to pin 2 []
		elif pin == 5:
			self._raw('\x1b\x70\x01') # Sends a pulse to pin 5 []
		else:
			raise CashDrawerError()


	def hw(self, hw):
		""" Hardware operations """
		if hw.upper() == "INIT":
			self._raw('\x1b\x40') # Clear data in buffer and reset modes
		elif hw.upper() == "SELECT":
			self._raw('\x1b\x3d\x01') # Printer select
		elif hw.upper() == "RESET":
			self._raw('\x1b\x3f\x0a\x00') # Reset printer hardware
		else: # DEFAULT: DOES NOTHING
			pass


	def control(self, ctl):
		""" Feed control sequences """
		if ctl.upper() == "LF": #Print buffer and line feed
			self._raw('\x0a')
		elif ctl.upper() == "FF": #Form Feed
			self._raw('\x0c')
		elif ctl.upper() == "CR": #Carriage Return
			self._raw('\x0d')
		elif ctl.upper() == "HT": #Horizontal Tab
			self._raw('\x09')
		elif ctl.upper() == "VT": #Vertical Tab
			self._raw('\x0b')


	def __del__(self):
		""" Release device interface """
		if self.handle:
			try:
				self.handle.releaseInterface()
				self.handle.resetEndpoint(self.out_ep)
				self.handle.reset()
			except Exception, err:
				print err
			self.handle, self.device = None, None
			# Give a chance to return the interface to the system
			# The following message could appear if the application is executed
			# too fast twice or more times.
			#
			# >> could not detach kernel driver from interface 0: No data available
			# >> No interface claimed
			time.sleep(1)

class Error(Exception):
    """ Base class for ESC/POS errors """
    def __init__(self, msg, status=None):
        Exception.__init__(self)
        self.msg = msg
        self.resultcode = 1
        if status is not None:
            self.resultcode = status

    def __str__(self):
        return self.msg

# Result/Exit codes
# 0  = success
# 50 = No string supplied to be printed
# 60 = Invalid pin to send Cash Drawer pulse

class TextError(Error):
    def __init__(self, msg=''):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 50

    def __str__(self):
        return _('Text string must be supplied to the text() method')


class CashDrawerError(Error):
    def __init__(self, msg=""):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 60

    def __str__(self):
        return _('Valid pin must be set to send pulse')

#Initiate the POSApplication class
if __name__ == "__main__":
	AppWindow = CounterLogic()
	gtk.main()
