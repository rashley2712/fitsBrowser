#!/usr/bin/env python

import datetime, collections
import argparse, sys, os, re, json, shutil, fcntl
import configHelper, numpy
import astropy
import scipy.ndimage
import scipy.misc
import fitsClasses
from astropy.io import fits
from PIL import Image,ImageDraw,ImageFont

debug = False
fh=0

def  run_once():
     global  fh
     lockFilename = "/tmp/fitsBrowser.lock"
     # first create a lock file if it doesn't already exist
     if not os.path.exists(lockFilename):
		 lockFile = open(lockFilename, 'wt')
		 lockFile.write("Lock file for fitsBrowser.py\n")
		 lockFile.close()
		 
     fh = open(lockFilename,'r')
     try:
         fcntl.flock(fh,fcntl.LOCK_EX|fcntl.LOCK_NB)
     except IOError as e:
		 print "Sorry. I think I might already be running, so I am going to exit. Please look for stray processes."
		 os._exit(0)

def readHeaderListFile(filename):
	headerListFile = open(filename, 'rt')
	headers = []
	for line in headerListFile:
		line = line.strip()
		if len(line)==0: continue   # The line is blank
		if line[0]=='#': continue   # The line is comment
		headers.append(line)
	print "Will search for the following FITS headers:", headers
	headerListFile.close()
	return headers
	
def writeJSONFile(filename, titleString, jsonData):
	jsFile = open(filename, 'wt')
	jsFile.write('var title= "%s";\n'%titleString)
	jsFile.write("var allImages= ")
	jsFile.write(json.dumps(jsonData, sort_keys=False))
	jsFile.write(";\n")
	jsFile.close()
	
			
	
def changeExtension(filename, extension):
	return os.path.splitext(filename)[0] + "." + extension 
	
if __name__ == "__main__":
	run_once()
	parser = argparse.ArgumentParser(description='Makes a web-browser accessible page containing previews and thumbnails of all FITS images in a directory.')
	parser.add_argument('--datapath', type=str, help='Path where the FITS files are. Default: current directory')
	parser.add_argument('--webpath', type=str, help='Path to write the web page and images to. Default: current directory')
	parser.add_argument('--installpath', type=str, help='Path of where this application has been installed. This is so that it can find the HTML files to copy to the web folder. ')
	parser.add_argument('--size', type=int, help='Thumbnail size. Default is 128 pixels.')
	parser.add_argument('--save', action="store_true", help='Write the input parameters to the config file as default values.')
	parser.add_argument('--skipallimages', action="store_true", help="Skip creating of the images and thumbnails, just create the metadata. (For debugging purposes)")
	parser.add_argument('--skipimages', action="store_true", help="Skip creating of the images (but still creates the thumbnails.")
	parser.add_argument('--html', action="store_true", help="Skip most of the work and just write the HTML pages to the destination folder.")
	parser.add_argument('-f', '--force', action="store_true", help="Force the re-creation of the PNG images and thumbnails. The default behaviour is to check the output folder to see if the PNG image already exists. If so, it skips the creation step. ")
	parser.add_argument('--debug', action="store_true", help="Show some debug information.")
	parser.add_argument('--headerlist', type=str, help='Filename of a text file containing FITS headers that should be displayed on the web page.')
	parser.add_argument('-n', '--number', type=int, default=0, help='Stop after processing ''--number'' images. Default is process all images.')
	parser.add_argument('-t', '--title', type=str, default="FITS Image browser for {today}", help='Title for the web page. Use {today} as an alias for today\'s date and {folder} for the source folder name.')
	
	args = parser.parse_args()
	if args.debug: debug = True
	if debug: print(args)
	
	forceImages = False
	if args.force: forceImages = True
	
	searchForHeaders = False
	skipthumbnails = False
	skipimages = False
	processAllImages = True
	if args.number>0: 	processAllImages=False
	if args.skipallimages:
		skipthumbnails = True
		skipimages = True
	if args.skipimages == True: skipimages = True
	# if args.skipthumbnails == True: skipthumbnails = True
		
	
	config = configHelper.configClass("fitsBrowser")
	configDefaults  = {
		"FITSPath": ".",
		"SearchString": ".*.(fits|fits.gz|fits.fz|fit)",
		"WebPath": ".",
		"InstallPath": "undefined", 
		"ThumbnailSize": 128, 
		"FITSHeadersList": "/home/rashley/fitHeaders.list"
	}
	config.setDefaults(configDefaults)
	rootPath = config.assertProperty("FITSPath", args.datapath)
	searchString = config.assertProperty("SearchString", None)
	webPath = config.assertProperty("WebPath", args.webpath)
	installPath = config.assertProperty("InstallPath", args.installpath)
	thumbnailSize = config.assertProperty("ThumbnailSize", args.size)
	fitsHeaderListFilename = config.assertProperty("FITSHeadersList", args.headerlist)
	if args.save:
		config.save()
	
	print "Install path:", installPath
	if installPath == "undefined": 
		print "Please specify the install path of fitsBrowser. Use the --installpath command option, or specify it in ~/.config/fitsBrowser/fitsBrowser.conf file."
		sys.exit(-1)
	
	if os.path.exists(fitsHeaderListFilename):
		print "Loading a header list file:", fitsHeaderListFilename
		headers = readHeaderListFile(fitsHeaderListFilename)
		if len(headers) > 0: searchForHeaders = True
		
	search_re = re.compile(searchString)
	
	# Create sub-folder for the images
	imageFolder = webPath + "/images"
	if debug: print "Creating folder %s"%imageFolder
	if not os.path.exists(imageFolder):
		os.makedirs(imageFolder)
	# Copy index.html file from source code folder to the web folder
	staticFiles = ["index.html", "jquery.js"]
	for s in staticFiles: shutil.copy2(installPath + "/" + s, webPath + "/" + s)
	if args.html: sys.exit()
	
	fitsFiles = []
	# Find all folders in data path
	folders = os.walk(rootPath)
	subFolders = []
	FITSFilenames = []
	for f in folders:
		if debug: print("Folder: %s"%os.path.realpath(f[0]))
		subFolders.append(os.path.realpath(f[0]))
		for file in f[2]:
			m = search_re.match(file)
			if (m): 
				FITSFilenames.append(file)

	
	print "subFolders:", subFolders
	mainFolderName = subFolders[0].split('/')
	print "Main folder:", mainFolderName[-1]
	print ("Found %d fits files in the folder."%len(FITSFilenames))
	
	# Now check in the destination folder for pre-existing data
	oldJSONdata = []
	if os.path.exists(webPath + '/imageMetadata.js'):
		jsFile = open(webPath + '/imageMetadata.js')
		for line in jsFile:
			if "var allImages" in line:
				jsData = line[len("var allImages= "):-2]
				oldJSONdata = json.loads(jsData)
				
	newFITSFilenames = []
	for f in FITSFilenames:
		newFile = True
		for j in oldJSONdata:
			if j['sourceFilename'] == f:
				if debug: print "Found file already....", f
				newFile = False
				break
		if newFile:
			newFITSFilenames.append(f)
			
	print "%d are new files."%len(newFITSFilenames)
	FITSFilenames = newFITSFilenames	
	jsonData = oldJSONdata
	
	# Prepare some of the JSON objects for writing
	titleString = args.title
	today = str(datetime.date.today()).replace('-','')
	folder = str(os.path.dirname(os.path.realpath(rootPath)))
	titleString = titleString.format(today = today, folder = folder)
	jsFilename = webPath + "/imageMetadata.js"
	
	
	writeJSONFile(jsFilename, titleString, jsonData)
	
	
	for index, f in enumerate(FITSFilenames):
		if debug: print "Filename:", f
		if not processAllImages and ((index)==args.number): break
		newImage = fitsClasses.fitsObject(debug=debug)
		if (newImage.initFromFITSFile(f, path=rootPath)==False): continue
		imageJSON = {}
		if not skipimages:
			imageFilename = imageFolder + "/" + changeExtension(newImage.filename, "png")
			if not os.path.exists(imageFilename) or forceImages:
				newImage.writeAsPNG(boosted=True, filename=imageFilename)
			else:
				if debug: print "Image exists, not overwriting."
			imageJSON['pngFilename'] = "images/" + changeExtension(newImage.filename, "png")
		imageFilename = imageFolder + "/thumb_" + changeExtension(newImage.filename, "png")
		if not os.path.exists(imageFilename) or forceImages:
			newImage.createThumbnail(filename=imageFilename, size=thumbnailSize)
		else:
			if debug: print "Thumbnail exists. Not overwriting."
		imageJSON['thumbnailFilename'] = "images/thumb_" + changeExtension(newImage.filename, "png")
		imageJSON['sourceFilename'] = newImage.filename
		imageJSON['xSize'] = newImage.size[0]
		imageJSON['ySize'] = newImage.size[1]
		if searchForHeaders:
			headerObject = collections.OrderedDict()
			for h in headers:
				try:
					headerObject.update(newImage.getHeader(h))
				except:
					print "No header data for", h
			imageJSON['headers'] = headerObject
				
		
		
		jsonData.append(imageJSON)
		writeJSONFile(jsFilename, titleString, jsonData)
	
		
		progressPercent = float(index+1) / float(len(FITSFilenames)) * 100.
		if not debug:
			sys.stdout.write("\rProgress:  %3.1f%%, %d of %d files. %s        "%(progressPercent, index+1, len(FITSFilenames), f))
			sys.stdout.flush()
		else:
			print "%s \tProgress:  %3.1f%%, %d of %d files."%(f, progressPercent, index+1, len(FITSFilenames))
		
	if not debug:
		sys.stdout.write("\n")
		sys.stdout.flush()	
	
	
	
	print ""
	print "Finished!"
	print "Point your browser at: %s"%("file://" + webPath + "/index.html")
