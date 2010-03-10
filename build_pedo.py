#!/usr/bin/python2.5
# -*- coding: utf-8 -*-
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
import py2deb
import os
if __name__ == "__main__":
    try:
        os.chdir(os.path.dirname(sys.argv[0]))
    except:
        pass
    print
    p=py2deb.Py2deb("pedometerhomewidget")   #This is the package name and MUST be in lowercase! (using e.g. "mClock" fails miserably...)
    p.description="Count the number of steps you've made using the N900's accelerometer."
    p.author="Andrei Mirestean"
    p.mail="andrei.mirestean@gmail.com"
    p.url="https://garage.maemo.org/projects/pedometerwidget/"
    p.depends = "python(>=2.5), python-gtk2, python-gobject, python-hildondesktop, python-hildon, python-cairo, hildon-desktop-python-loader, python-gconf, python-xml, python-gst0.10"
    p.section="user/desktop"
    p.icon = "/home/andrei/pedometer-widget-0.1/icon.png"
    p.arch="all"                #should be all for python, any for all arch
    p.urgency="low"             #not used in maemo onl for deb os
    p.distribution="fremantle"
    p.repository="extras-devel"
    p.xsbc_bugtracker="https://garage.maemo.org/tracker/?group_id=1272"
    p.maemodisplayname = "Pedometer Home Widget"
    p.postinstall="""#!/bin/sh
    GCONF_CONFIG_SOURCE=`gconftool-2 --get-default-source` \
              gconftool-2 --makefile-install-rule /etc/gconf/schemas/pedometer.schemas""" #Set here your post install script
    #  p.postremove="""#!/bin/sh
    #  chmod +x /usr/bin/mclock.py""" #Set here your post remove script
    #  p.preinstall="""#!/bin/sh
    #  chmod +x /usr/bin/mclock.py""" #Set here your pre install script
    #  p.preremove="""#!/bin/sh
    #  chmod +x /usr/bin/mclock.py""" #Set here your pre remove script
    version = "0.3"           #Version of your software, e.g. "1.2.0" or "0.8.2"
    build = "1"                 #Build number, e.g. "1" for the first build of this version of your software. Increment for later re-builds of the same version of your software.
    #Text with changelog information to be displayed in the package "Details" tab of the Maemo Application Manager
    changeloginformation ="New features: \n*fixed Imperial units bug\n*option to set sensitivity\n*options to set step length\n*calculate number of lost calories\n*show graphs of steps/distance/calories\n*save history in XML file\n*set alarm for steps/calories/distance\n*option to pause timer when not walking"
    dir_name = "src"            #Name of the subfolder containing your package source files (e.g. usr\share\icons\hicolor\scalable\myappicon.svg, usr\lib\myapp\somelib.py). We suggest to leave it named src in all projects and will refer to that in the wiki article on maemo.org
    for root, dirs, files in os.walk(dir_name):
        real_dir = root[len(dir_name):]
        fake_file = []
        for f in files:
            fake_file.append(root + os.sep + f + "|" + f)
        if len(fake_file) > 0:
            p[real_dir] = fake_file
    print p
    r = p.generate(version,build,changelog=changeloginformation,tar=True,dsc=True,changes=True,build=False,src=True)
