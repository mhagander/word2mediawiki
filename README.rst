==============
Word2Mediawiki
==============

This project contains some "fairly simple" scripts to deal with automated
best-effort conversion from Word (or OpenOffice/LibreOffice) to Mediawiki.
Each file converted will create a page on the wiki, where all the
textual content will go, and also automatically upload all related images
to the wiki as attachments.

Copyright
---------
::

	Author: Magnus Hagander <magnus.hagander@redpill-linpro.com>
	Based on work from Lars Strand <lars@redpill-linpro.no>
	Work commissioned by Oslo Lufthavn AS, 2011 osl-nett@osl.no

	(C) 2011

	Licensed under the GNU LGPL v2.1 - http://www.gnu.org/licenses/lgpl-2.1.html
	- or any later version.

Credits
+++++++
This project is based off work by *Lars Strand*, cleaned up and re-implemented
in a single language, with proper error checking etc. For document conversion,
it uses *DocumentConverter.py* by *Mirko Nasato*. Finally, the uploading to
*mediawiki* is made using the *Python Wikipedia Robot Framework*.


Requirements
------------
The system has so far been tested only on Ubuntu, but should work on any
system that can provide the required software. The following Ubuntu packages
are required (on top of the base system, and of course including any
dependencies they required):

* python-magic
* python-uno
* openoffice.org-java-common
* openoffice.org-wiki-publisher
* openoffice.org-writer

Other than this, a checkout of
http://svn.wikimedia.org/svnroot/pywikipedia/trunk/pywikipedia
needs to be made into the subdirectory *pywikipedia*.

Operations
----------
The basic script is ``word2mediawiki.py``, and is executed once per file,
specifying the file name on the command line. The script performs several
actions in a flow:

#. The file is converted, using functions from *DocumentConverter.py*, to
   *both* XML and wiki markup, in a temporary working directory.
#. The returned XML file is then parsed for all image contents, since the wiki
   file does not include them. The images are stored in the XML file in
   base64 encoded format. The images are given sequential numbers that are later
   used for references and file names.
#. The returned wiki file is then parsed, and all instances of images (which
   at this point have no names) are replaced with explicit references to the
   image names generated in the previous step. The wiki text is also assigned	
   to the category *word2mediawiki*, for easier tracking.
#. A login attempt is made to the wiki (this is an uncertain step, it sometimes
   returns successful login even when it doesn't work, but it's a necessary	
   step).
#. The wiki is checked for presence of a document with this name. It checks both
   for a page with this name, and for uploaded files conflicting with the names
   of our generated images. If a file exists, a simple suffix counter is added
   to the name and it's tried again, to attempt to get around the naming
   conflict.
#. Once we have all this data, the page is uploaded. First the page itself,
   then all the images, and finally a copy of the original word document for
   reference.

Setting up
----------
The first step of setting up, is to create a *family* for *pywikipedia* to use
for logging in. This is done by editing the file *pywikipedia/families/test_family.py* (replace *test* with whatever is reasonable in your setup, for example
*osl*). This file should contain something like ::

	# -*- coding: utf-8  -*-
	import family

	class Family(family.Family):
	      def __init__(self):
	      	  family.Family.__init__(self)
	    	  self.name = 'test' #Set the family name; this should be the same as in the file name.

	    	  self.langs = {
	    	       'en': None,
	    	  }

	      def hostname(self, code):
	      	  return 'wiki.somewhere.com'

	      def version(self, code):
              	  return "1.12.0"

	      def scriptpath(self, code):
	      	  return '/mediawiki'

(Obviously changed to suit the environment).

When this file is in place, run the login script from *pywikipedia* once
(seems to sometimes be necessary, sometimes not, so just do it..) ::

	cd pywikipedia
	python login.py -force

In the order of the questions returned, enter:

#. The id of the new family you created earlier
#. The language (normally just pick the default)
#. The user name (must be entered, don't use the default)
#. Small configuration
#. Your password

Once this is done, update the *word2mediawiki.ini* file with family, password
and language.

Cron job
--------
If you want the system to run automatically, just put the convert_cron.sh
script in cron at a suitable interval. You may need to edit this script to
change paths etc.

When running this from cron, make sure that the user who's running it (which
should never be *root*, of course) has permissions on at least the following
directories (rooted in the installation directory):

* log
* share
* tmp
* pywikipedia/logs
* pywikipedia/login-data
