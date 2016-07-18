#!/usr/bin/env python

import argparse, sys, os, re, json, shutil, datetime, subprocess, fcntl
import configHelper, numpy

def debug(output):
	global debugLevel
	if not debugLevel: return
	print(str(output))
	
fh=0

def  run_once():
     global  fh
     lockFilename = "/tmp/dayBuilder.lock"
     # first create a lock file if it doesn't already exist
     if not os.path.exists(lockFilename):
		 lockFile = open(lockFilename, 'wt')
		 lockFile.write("Lock file for dayBuilder.py\n")
		 lockFile.close()
    
     fh = open("/tmp/block", 'r')
     try:
         fcntl.flock(fh,fcntl.LOCK_EX|fcntl.LOCK_NB)
         # fcntl.flock(fh,fcntl.LOCK_EX)
     except IOError as e:
		 print "Sorry. I think I might already be running, so I am going to exit. Please look for stray processes."
		 print e
		 os._exit(0)

	
if __name__ == "__main__":
	run_once()
	debugLevel = 0
	parser = argparse.ArgumentParser(description='Builds or updates a root web folder containing fitsBrowser sub-folders for each day..')
	parser.add_argument('--datapath', type=str, help='Path where the FITS files are. Default: current directory')
	parser.add_argument('webpath', type=str, help='Path to write the web page and images to. ')
	parser.add_argument('--installpath', type=str, help='Path of where this application has been installed. This is so that it can find the HTML files to copy to the web folder. ')
	parser.add_argument('--debug', action='store_true', help='Debug')
	parser.add_argument('--copyonly', action='store_true', help='Only copy the html files and then exit.')
	parser.add_argument('--date', default='{today}', help='Date to process for the sub-folder. Default is {today}. Can also use {yesterday}.')
	args = parser.parse_args()
	if args.debug: debugLevel = 1
	debug(args)
	
	config = configHelper.configClass("fitsBrowser")
	webPath = config.assertProperty("WebPath", args.webpath)
	installPath = config.assertProperty("InstallPath", args.installpath)
	dataPath = config.assertProperty("DataPath", args.datapath)
	
	debug(config)
	
	# Now run 'fitBrowser'
	if args.date == "{today}":
		dateFolder = str(datetime.date.today()).replace('-','')
	elif args.date == "{yesterday}":
		dateFolder = str(datetime.date.today() - datetime.timedelta(days=1)).replace('-', '')
	else:
		dateFolder = args.date
	dataFolder = dataPath + "/" + dateFolder
	
	# First, check if the source data is there
	if not os.path.exists(dataPath):
		print "The folder for the source data %s could not be found. Exiting."%dataPath
		sys.exit()
	if not os.path.exists(dataFolder):
		print "The folder for the source data %s could not be found. Exiting."%dataFolder
		sys.exit()
	
	# Second, check to see if the webpath already exists
	if not os.path.exists(webPath):
		debug("Creating folder %s"%webPath)
		os.makedirs(webPath)
		
		
	# Copy the needed files into the destination folder
	fileList = ['rootpage.html', 'jquery.js']
	for f in fileList: shutil.copy2(installPath + "/" + f, webPath + "/" + f)
	
	# Exit now if '--copyonly is specified
	if args.copyonly: sys.exit()
	
	
	outputFolder = webPath + "/" + dateFolder
	debug("Looking for FITS files in folder: %s"%dataFolder)
	debug("Writing to: %s"%outputFolder)
	
	fitsBrowserCommand = [installPath + "/fitsBrowser.py"]
	fitsBrowserCommand.append('--datapath')
	fitsBrowserCommand.append(dataFolder)
	fitsBrowserCommand.append('--webpath')
	fitsBrowserCommand.append(outputFolder)
	fitsBrowserCommand.append('--title')
	fitsBrowserCommand.append('INT images for ' + dateFolder)
					
	subprocess.call(fitsBrowserCommand)
		
	
