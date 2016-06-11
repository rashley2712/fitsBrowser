#!/usr/bin/env python

import argparse, sys, os, re, json, shutil, datetime, subprocess
import configHelper, numpy

def debug(output):
	global debugLevel
	if not debugLevel: return
	print(str(output))
	
if __name__ == "__main__":
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
	
	debug(config)
	
	# First check to see if the webpath already exists
	if not os.path.exists(args.webpath):
		debug("Creating folder %s"%args.webpath)
		os.makedirs(args.webpath)
		
		
	# Copy the needed files into the destination folder
	fileList = ['rootpage.html', 'jquery.js']
	for f in fileList: shutil.copy2(installPath + "/" + f, webPath + "/" + f)
	
	# Exit now if '--copyonly is specified
	if args.copyonly: sys.exit()
	
	# Now run 'fitBrowser'
	if args.date == "{today}":
		dateFolder = str(datetime.date.today()).replace('-','')
	elif args.date == "{yesterday}":
		dateFolder = str(datetime.date.today() - datetime.timedelta(days=1)).replace('-', '')
	else:
		dateFolder = args.date
	debug("Looking in sub folder: %s"%dateFolder)
	
	outputFolder = webPath + "/" + dateFolder
	debug("Writing to: %s"%outputFolder)
	
	fitsBrowserCommand = [installPath + "/fitsBrowser.py"]
	fitsBrowserCommand.append('--datapath')
	fitsBrowserCommand.append(dateFolder)
	fitsBrowserCommand.append('--webpath')
	fitsBrowserCommand.append(outputFolder)
	fitsBrowserCommand.append('--title')
	fitsBrowserCommand.append('INT images for ' + dateFolder)
					
	subprocess.call(fitsBrowserCommand)
		
	
