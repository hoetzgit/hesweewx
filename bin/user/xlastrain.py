# extended stats based on the xsearch example
# $Id: xstats.py 2749 2014-11-29 18:15:24Z tkeffer $
# Copyright 2013 Matthew Wall, all rights reserved

"""This search list extension offers extra tags:

  'lastrain_day': dd.mm.YYYY HH:MM
  'lastrain_delta_time': now - lastrain_day in s

  Der letzte Regen am dd.mm.YYYY HH:MM das war vor xx Tagen, xx Stunden, xx Minuten
"""
import datetime
import time

from weewx.cheetahgenerator import SearchList
from weewx.tags import TimespanBinder
from weeutil.weeutil import TimeSpan
from weewx.units import ValueHelper

class MyXLastrain(SearchList):
    
    def __init__(self, generator):
        SearchList.__init__(self, generator)
  
    def get_extension_list(self, timespan, db_lookup):
        """Returns a search list extension with additions.

        timespan: An instance of weeutil.weeutil.TimeSpan. This holds
                  the start and stop times of the domain of valid times.

        db_lookup: Function that returns a database manager given a
                   data binding.
        """

        # First, create a TimespanBinder object for all time. This one is easy
        # because the object timespan already holds all valid times to be
        # used in the report.
        _row = db_lookup().getSql("SELECT MAX(dateTime) FROM archive_day_rain WHERE sum > 0")
        lastrain_ts = _row[0]
        # Now if we found a ts then use it to limit our search on the archive
        # so we can find the last archive record during which it rained. Wrap
        # in a try statement just in case
        if lastrain_ts is not None:
            try:
                _row = db_lookup().getSql("SELECT MAX(dateTime) FROM archive WHERE rain > 0 AND dateTime > ? AND dateTime <= ?", (lastrain_ts, lastrain_ts + 86400))
                lastrain_ts = _row[0]
            except:
                lastrain_ts = None
        # Wrap our ts in a ValueHelper
        lastrain_vt = (lastrain_ts, 'unix_epoch', 'group_time')
        lastrain_vh = ValueHelper(lastrain_vt, formatter=self.generator.formatter, converter=self.generator.converter)

	# next idea stolen with thanks from weewx station.py
        # note this is delta time from 'now' not the last weewx db time
        delta_time = time.time() - lastrain_ts if lastrain_ts else None

        # Wrap our ts in a ValueHelper
        delta_time_vt = (delta_time, 'second', 'group_deltatime')
        delta_time_vh = ValueHelper(delta_time_vt, formatter=self.generator.formatter, converter=self.generator.converter)
        

        
        return [{'lastrain_day': lastrain_vh,
                 'lastrain_delta_time': delta_time_vh}]


