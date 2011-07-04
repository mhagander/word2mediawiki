#!/usr/bin/env python
# -*- coding: utf-8  -*-

# -------------------------------
# Author: Magnus Hagander <magnus.hagander@redpill-linpro.com>
# Based on work from Lars Strand <lars@redpill-linpro.no>
# Work commissioned by Oslo Lufthavn AS, 2011 osl-nett@osl.no
# (C) 2011
#
# Licensed under the GNU LGPL v2.1 - http://www.gnu.org/licenses/lgpl-2.1.html
# - or any later version.
# -------------------------------

## Some static settings - only change when sure what you're doing
##  (normal settings are in word2mediawiki.ini
allowedextensions=('odt', 'doc')

import os
import sys
import re
import magic
import traceback
import codecs

from xml.etree.ElementTree import XMLParser
from DocumentConverter import DocumentConverter
from base64 import b64decode
from ConfigParser import ConfigParser
from optparse import OptionParser

# Mediawiki API imports (assuming subdirectory pywikipedia is available)
sys.path.append('pywikipedia')
# Need to clean out argv since pywikipedia bot parses it directly..
argvcopy = sys.argv
sys.argv = sys.argv[0:1]

import wikipedia
from wikipedia import Page
from login import LoginManager
from upload import UploadRobot
from pywikibot.exceptions import PageNotSaved

# Initialize global state
re_imagematch = re.compile('(\[\[Image:([^\]]+)?\]\])')
images = []

# We need the magic matcher initialized to determine what type of images
# are to be sent.
ms = magic.open(magic.MAGIC_NONE)
ms.load()


# ----------------
# Utilitiy classes
# ----------------

# Wrapper to we answer all prompts, since pywikipediabot isn't
# intended to be scripted this way. We expect we're only going to get
# prompted about warnings, so we always say yes.
# This class will also capture standard output, since the pywikipediabot
# classes are *extremely* chatty.
class IOWrapper():
	def __init__(self, activity):
		if options.verbose:
			print activity

	def readline(self):
		# Wrapper for stdin
		return 'Y'

	def write(self, str):
		# Wrapper for stdout
		self.collected.append(str)

	def __enter__(self):
		self.stdin = sys.stdin
		self.stdout = sys.stdout
		self.stderr = sys.stderr
		sys.stdin = self
		sys.stdout = self
		sys.stderr = self
		self.collected = []

	def __exit__(self, type, value, tb):
		sys.stdin = self.stdin
		sys.stdout = self.stdout
		sys.stderr = self.stderr
		if value:
			# Some kind of exception
			sys.stderr.write("An exception occurred:\n")
			traceback.print_exception(type, value, tb)
			sys.stderr.write("Collected data:\n")
			sys.stderr.write(''.join(self.collected))
			sys.exit(1)
		# No exception, so just return and keep running, unless we
		# are running in debug mode.
		if options.debug:
			print ''.join(self.collectged)

# Wraps a simple image, for storing in an array
class ImageWrapper(object):
	def __init__(self, imgbuf):
		self.buffer = imgbuf
		self.mimetype = ms.buffer(imgbuf)

	def extension(self):
		if self.mimetype.find('PNG') >= 0:
			return 'png'
		if self.mimetype.find('JPG') >= 0 or self.mimetype.find('JPEG') >= 0:
			return 'jpg'
		print "Unknown image type '%s'" % self.mimetype
		return 'bin'


# Handler class for ElementTree parser, that grabs all images and adds
# them to the global array "images".
class ImageGrabber(object):
	def start(self, tag, attrib):
		if tag == '{http://www.w3.org/1999/xhtml}img':
			if attrib['src'].startswith('data:image/*;base64,'):
				images.append(ImageWrapper(b64decode(attrib['src'][20:])))
			else:
				print "Image found with incorrect start, ignoring"
	def end(self, tag):
		pass
	def data(self, data):
		pass
	def close(self):
		pass

# ----------------
# Main entrypoint
# ----------------

if __name__ == "__main__":
	cp = ConfigParser()
	cp.read('word2mediawiki.ini')
	tempdir = cp.get('word2mediawiki', 'tempdir')
	family = cp.get('mediawiki', 'family')
	password = cp.get('mediawiki', 'password')
	language = cp.get('mediawiki', 'language')

	# Get any commandline parameters
	opt = OptionParser()
	opt.add_option('-v', '--verbose', dest='verbose', action='store_true', help='Run in verbose mode', default=False)
	opt.add_option('-d', '--debug', dest='debug', action='store_true', help='Run in debug mode', default=False)
	(options, args) = opt.parse_args(argvcopy[1:])
	if len(args) != 1:
		opt.print_help()
		sys.exit(1)
	inputfile = args[0]

	# Validate the doc exists
	if not os.path.exists(inputfile):
		print "Input file '%s' does not exist" % inputfile
		sys.exit(1)

	# Determine and validate base name and extension
	(baseoutname, docextension) = os.path.splitext(inputfile)
	baseoutname = os.path.basename(baseoutname)
	docextension=docextension[1:] # Remove leading period
	if not docextension.lower() in allowedextensions:
		print "Unknown extension '%s'" % docextension.lower()
		print "Only %s are allowed" % ", ".join(allowedextensions)
		sys.exit(1)

	# Clean up any old files
	for f in ('%s/converted.wiki' % tempdir, '%s/converted.xml' % tempdir):
		if os.path.exists(f): os.unlink(f)


	# Convert the actual document. This will always create temporary files,
	# there is no way to get the data in a buffer.
	with IOWrapper("Converting document format..."):
		converter = DocumentConverter()
		converter.convert(inputfile, '%s/converted.wiki' % tempdir)
		converter.convert(inputfile, '%s/converted.xml' % tempdir)

	# Read the converted wiki format, and append our hardcoded additions
	wf = codecs.open('%s/converted.wiki' % tempdir, "r", "utf-8")
	wikilines = wf.readlines()
	wf.close()
	wikilines.append("\n[[Category:word2mediawiki]]\n")

	# Grab images out of the XML data
	parser = XMLParser(target=ImageGrabber())
	parser.feed(open('%s/converted.xml' % tempdir).read())
	parser.close()

	# Prepare for uploading to mediawiki
	# Make sure we are logged in
	with IOWrapper("Logging in..."):
		site = wikipedia.getSite(language, family)
		if not site.loggedInAs():
			lm = LoginManager(site=site, password=password)
			if lm.login(retry=True):
				site._isLoggedIn[0] = True
				site._userName[0] = lm.username
				site._userData[0] = False

	# Make sure all the filenames we want to use are empty, and if not, twiddle
	# the filename until they are.
	outnamecounter = 0
	while True:
		if outnamecounter > 0:
			outname = "%s_%s" % (baseoutname, outnamecounter)
		else:
			outname = baseoutname
		outnamecounter += 1
		if outnamecounter > 50:
			print "Tried 50 different names, it's probably something else that's wrong."
			print "Giving up."
			sys.exit(1)

		# Check for existing copy of either a page with this very name, or
		# of one of our attached files. If any of them alerady exist, loop
		# back up and try another name.
		with IOWrapper("Checking whether '%s' exists..." % outname):
			if Page(site, outname).exists():
				print "Page %s already exists, trying another name" % outname
				continue

		with IOWrapper("Checking whether 'File:%s.%s' exists..." % (outname, docextension)):
			if Page(site, "File:%s.%s" % (outname, docextension)).exists():
				print "File %s already exists, trying another name" % ("File:%s.%s" % (outname, docextension))
				continue

		for i in range(0, len(images)):
			foundany = False
			with IOWrapper("Checking whether 'File:%s_%s.%s' exists..." % (outname, i, images[i].extension())):
				if Page(site, "File:%s_%s.%s" % (outname, i, images[i].extension())).exists():
					print "Image %s already exists, trying another name" % ("File:%s_%s.%s" % (outname, i, images[i].extension()))
					foundany = True
					break

		if foundany: continue

		# At this point, we *think* the page is not there. However, if a page
		# has been deleted in mediawiki, the API will claim it is not there,
		# but it is still not possible to create it under that name. So we
		# have to actually create it here, and give up and try another name
		# if it fails.
		# In a great show of consistency, this only applies to pages and not to
		# files, it seems...

		# Since we have the names of the images in the file, we need to
		# recompute and substitute that at each entry into this loop.
		imgidx = 0
		for i in range(0,len(wikilines)):
			if re_imagematch.search(wikilines[i]):
				wikilines[i] = re_imagematch.sub('[[Image:%s_%s.%s]]' % (outname, imgidx, images[imgidx].extension()), wikilines[i])
				imgidx += 1
		if imgidx != len(images):
			# Mismatch between found images and found image tags
			print "Did not find match for all images!"
			sys.exit(1)

		# Attempt the base page upload
		with IOWrapper("Uploading page..."):
			try:
				p = Page(site, outname)
				p.put(''.join(wikilines), comment='Uploaded by word2mediawiki',
					  minorEdit=True, force=True)
			except PageNotSaved:
				# Ok, failed. So let's retry with another name
				continue

		# Now that the page is created, we will no longer be able to retry
		# with a better name, so let's just abort if things fail from here on.
		# Thus, drop out of the loop
		break

	# Upload the base document, assuming nobody else has uploaded a document
	# between us checking it and actuall uploading.
	with IOWrapper("Uploading base document..."):
		bot = UploadRobot(inputfile,
						  description='Uploaded by word2mediawiki',
						  useFilename="%s.%s" % (outname, docextension),
						  keepFilename=True, verifyDescription=False)
		bot.run()

	# Upload all images (same assumption as for base document)
	for i in range(0,len(images)):
		img = images[i]
		with IOWrapper("Uploading image %s of %s..." % (i+1, len(images))):
			bot = UploadRobot("http://devnull",
							  description="Uploaded by word2mediawiki for inclusion in %s" % outname,
							  useFilename="%s_%s.%s" % (outname, i, img.extension()),
							  keepFilename=True, verifyDescription=False)
			bot._contents = img.buffer
			bot.run()

	# Clean up any old files
	for f in ('%s/converted.wiki' % tempdir, '%s/converted.xml' % tempdir):
		if os.path.exists(f): os.unlink(f)
