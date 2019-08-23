# coding=utf-8
# $Id: dwdmon.py 1790 2019-01-10 06:31:32Z hes $
# Copyright 2019 Hartmut Schweidler
# Original by Matthew Wall

""" weewx.conf

copy 'dwdmon.py' to /home/weewx/bin/user


[DWDPollen]
    data_binding = dwd_binding
    max_age = 604800     # 7 days; None to store indefinitely
    interval = 39600     # 11 Stunden

    [[Pollen]]
        max_age = 604800     # 7 days; None to store indefinitely
        interval = 39600     # 11 Stunden


[Engine]

    [[Services]]

        archiv_services = ..., user.dwdmon.DWD

"""

from __future__ import absolute_import

import logging
import calendar
import configobj
import datetime
import gzip
import hashlib
import http.client
import os, errno
import re
import socket
import string
import subprocess
import threading
import time
import urllib.request, urllib.error, urllib.parse

import json

from io import StringIO

#try:
#    import cjson as json
#    setattr(json, 'dumps', json.encode)
#    setattr(json, 'loads', json.decode)
#except (ImportError, AttributeError):
#    try:
#        import simplejson as json
#    except ImportError:
#        import json

import weewx
import weedb
import weewx.manager
import weeutil.weeutil
from weewx.engine import StdService
from weewx.cheetahgenerator import SearchList

log = logging.getLogger(__name__)

VERSION = "3.3.1"


def mkdir_p(path):
    """equivalent to 'mkdir -p'"""
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

schema = [('method',     'VARCHAR(10) NOT NULL'),
          ('dateTime',   'INTEGER NOT NULL'),
          ('usUnits',    'INTEGER NOT NULL'),
          ('issued_ts',  'INTEGER NOT NULL'),
          ('event_ts',   'INTEGER NOT NULL'),
          ('duration',   'INTEGER'),
          ('up_date',    'INTEGER'),
          ('next_date',  'INTEGER'),
          ('region',     'VARCHAR(64)'),
          ('region_id',  'VARCHAR(4)'),
          ('hasel_h',    'VARCHAR(4)'),
          ('erle_h',     'VARCHAR(4)'),
          ('esche_h',    'VARCHAR(4)'),
          ('birke_h',    'VARCHAR(4)'),
          ('graeser_h',  'VARCHAR(4)'),
          ('roggen_h',   'VARCHAR(4)'),
          ('beifuss_h',  'VARCHAR(4)'),
          ('ambrosia_h', 'VARCHAR(4)'),
          ('hasel_m',    'VARCHAR(4)'),
          ('erle_m',     'VARCHAR(4)'),
          ('esche_m',    'VARCHAR(4)'),
          ('birke_m',    'VARCHAR(4)'),
          ('graeser_m',  'VARCHAR(4)'),
          ('roggen_m',   'VARCHAR(4)'),
          ('beifuss_m',  'VARCHAR(4)'),
          ('ambrosia_m', 'VARCHAR(4)'),
          ('hasel_n',    'VARCHAR(4)'),
          ('erle_n',     'VARCHAR(4)'),
          ('esche_n',    'VARCHAR(4)'),
          ('birke_n',    'VARCHAR(4)'),
          ('graeser_n',  'VARCHAR(4)'),
          ('roggen_n',   'VARCHAR(4)'),
          ('beifuss_n',  'VARCHAR(4)'),
          ('ambrosia_n', 'VARCHAR(4)'),
          ]


DEFAULT_BINDING_DICT = {
    'database': 'dwd_sqlite',
    'manager': 'weewx.manager.Manager',
    'table_name': 'archive',
    'schema': 'user.pollenmon.schema'}

class DwdpollenThread(threading.Thread):
    def __init__(self, target, *args):
        self._target = target
        self._args = args
        threading.Thread.__init__(self)

    def run(self):
        self._target(*self._args)

class DWDPollen(StdService):
    """Base class for dwdpollening services."""

    def __init__(self, engine, config_dict, fid,
                 interval=1800, max_age=604800):
        super(DWDPollen, self).__init__(engine, config_dict)
        log.info('%s: DWD version %s',  fid, VERSION)
        self.method_id = fid

        # single database for all different types of dwdpollens
        d = config_dict.get('DWDPollen', {})
        self.binding = d.get('data_binding', 'dwd_binding')

        # these options can be different for each dwdpollen method

        # how often to do the dwdpollen
        self.interval = self._get_opt(d, fid, 'interval', interval)
        self.interval = int(self.interval)
        # how long to keep dwdpollen records
        self.max_age = self._get_opt(d, fid, 'max_age', max_age)
        self.max_age = self.toint('max_age', self.max_age, None, fid)
        # option to vacuum the sqlite database
        self.vacuum = self._get_opt(d, fid, 'vacuum', False)
        self.vacuum = weeutil.weeutil.tobool(self.vacuum)
        # how often to retry database failures
        self.db_max_tries = self._get_opt(d, fid, 'database_max_tries', 3)
        self.db_max_tries = int(self.db_max_tries)
        # how long to wait between retries, in seconds
        self.db_retry_wait = self._get_opt(d, fid, 'database_retry_wait', 10)
        self.db_retry_wait = int(self.db_retry_wait)
        # use single_thread for debugging
        self.single_thread = self._get_opt(d, fid, 'single_thread', False)
        self.single_thread = weeutil.weeutil.tobool(self.single_thread)
        # option to save raw dwdpollen to disk
        self.save_raw = self._get_opt(d, fid, 'save_raw', False)
        self.save_raw = weeutil.weeutil.tobool(self.save_raw)
        # option to save failed foreast to disk for diagnosis
        self.save_failed = self._get_opt(d, fid, 'save_failed', False)
        self.save_failed = weeutil.weeutil.tobool(self.save_failed)
        # where to save the raw dwdpollens
        self.diag_dir = self._get_opt(d, fid, 'diagnostic_dir', '/var/tmp/fc')
        # how long to wait before doing the dwdpollen
        self.delay = int(self._get_opt(d, fid, 'delay', 0))

        self.last_ts = 0
        self.updating = False
        self.last_raw_digest = None
        self.last_fail_digest = None

        # setup database
        dbm_dict = weewx.manager.get_manager_dict(
            config_dict['DataBindings'], config_dict['Databases'], self.binding,
            default_binding_dict=DEFAULT_BINDING_DICT)
        with weewx.manager.open_manager(dbm_dict, initialize=True) as dbm:
            # ensure schema on disk matches schema in memory
            dbcol = dbm.connection.columnsOf(dbm.table_name)
            memcol = [x[0] for x in dbm_dict['schema']]
            if dbcol != memcol:
                raise Exception('%s: schema mismatch: %s != %s' %
                                (self.method_id, dbcol, memcol))
            # find out when the last dwdpollen happened
            self.last_ts = DWDPollen.get_last_dwdpollen_ts(dbm, self.method_id)

    def _bind(self):
        # ensure that the dwdpollen has a chance to update on each new record
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.update_dwdpollen)

    def _get_opt(self, d, fid, label, default_v):
        """get an option from dict, prefer specialized value if one exists"""
        v = d.get(label, default_v)
        dd = d.get(fid, {})
        v = dd.get(label, v)
        return v

    @staticmethod
    def toint(label, value, default_value, method):
        """convert to integer but also permit a value of None"""
        if isinstance(value, str) and value.lower() == 'none':
            value = None
        if value is not None:
            try:
                value = int(value)
            except ValueError:
                log.error("%s: bad value '%s' for %s",
                            method, value, label)
                value = default_value
        return value

    @staticmethod
    def str2int(n, s, method):
        if s is not None and s != '':
            try:
                return int(s)
            except (ValueError, TypeError) as e:
                log.error("%s: conversion error for %s from '%s': %s",
                            method, n, s, e)
        return None

    @staticmethod
    def str2float(n, s, method):
        if s is not None and s != '':
            try:
                return float(s)
            except (ValueError, TypeError) as e:
                log.error("%s: conversion error for %s from '%s': %s",
                            method, n, s, e)
        return None

    @staticmethod
    def save_fc_data(fc, dirname, basename='dwdpollen-data', msgs=None):
        """save raw dwdpollen data to disk, typically for diagnostics"""
        ts = int(time.time())
        tstr = time.strftime('%Y%m%d%H%M', time.localtime(ts))
        mkdir_p(dirname)
        fn = '%s/%s-%s' % (dirname, basename, tstr)
        with open(fn, 'w') as f:
            if msgs is not None:
                for m in msgs:
                    f.write("%s\n" % m)
            f.write(fc)

    def save_raw_dwdpollen(self, fc, basename='raw', msgs=None):
        m = hashlib.md5()
        m.update(fc)
        digest = m.hexdigest()
        if self.last_raw_digest == digest:
            return
        DWDPollen.save_fc_data(fc, self.diag_dir, basename=basename, msgs=msgs)
        self.last_raw_digest = digest

    def save_failed_dwdpollen(self, fc, basename='fail', msgs=None):
        m = hashlib.md5()
        m.update(fc)
        digest = m.hexdigest()
        if self.last_fail_digest == digest:
            return
        DWDPollen.save_fc_data(fc, self.diag_dir, basename=basename, msgs=msgs)
        self.last_fail_digest = digest

    def update_dwdpollen(self, event):
        if self.single_thread:
            self.do_dwdpollen(event)
        elif self.updating:
            log.debug('%s: update thread already running', self.method_id)
        elif time.time() - self.interval > self.last_ts:
            t = DwdpollenThread(self.do_dwdpollen, event)
            t.setName(self.method_id + 'Thread')
            log.debug('%s: starting thread', self.method_id)
            t.start()
        else:
            log.debug('%s: not yet time to do the dwdpollen', self.method_id)

    def do_dwdpollen(self, event):
        self.updating = True
        try:
            if self.delay:
                time.sleep(self.delay)
            records = self.get_dwdpollen(event)
            if records is None:
                return
            dbm_dict = weewx.manager.get_manager_dict(
                self.config_dict['DataBindings'],
                self.config_dict['Databases'],
                self.binding,
                default_binding_dict=DEFAULT_BINDING_DICT)
            with weewx.manager.open_manager(dbm_dict) as dbm:
                DWDPollen.save_dwdpollen(dbm, records, self.method_id,
                                       self.db_max_tries, self.db_retry_wait)
                self.last_ts = int(time.time())
                if self.max_age is not None:
                    DWDPollen.prune_dwdpollens(dbm, self.method_id,
                                             self.last_ts - self.max_age,
                                             self.db_max_tries,
                                             self.db_retry_wait)
                if self.vacuum:
                    DWDPollen.vacuum_database(dbm, self.method_id)
        except Exception as e:
            log.error('%s: DWD failure: %s', self.method_id, e)
            #weeutil.weeutil.log_traceback(loglevel=syslog.LOG_DEBUG)
        finally:
            log.debug('%s: terminating thread', self.method_id)
            self.updating = False

    def get_dwdpollen(self, event):
        """get the dwdpollen, return an array of dwdpollen records."""
        return None

    @staticmethod
    def get_last_dwdpollen_ts(dbm, method_id):
        sql = "select dateTime,issued_ts from %s where method = '%s' and dateTime = (select max(dateTime) from %s where method = '%s') limit 1" % (dbm.table_name, method_id, dbm.table_name, method_id)
        r = dbm.getSql(sql)
        if r is None:
            return None
        log.debug('%s: last DWDPollen issued %s, requested %s',
                    method_id,
                    weeutil.weeutil.timestamp_to_string(r[1]),
                    weeutil.weeutil.timestamp_to_string(r[0]))
        return int(r[0])

    @staticmethod
    def save_dwdpollen(dbm, records, method_id, max_tries=3, retry_wait=10):
        for count in range(max_tries):
            try:
                log.debug('%s: saving %d DWDPollen records',
                            method_id, len(records))
                dbm.addRecord(records, log_level=syslog.LOG_DEBUG)
                log.info('%s: saved %d dwdpollen records',
                           method_id, len(records))
                break
            except weedb.DatabaseError as e:
                log.error('%s: save failed (attempt %d of %d): %s',
                            method_id, (count + 1), max_tries, e)
                log.debug('%s: waiting %d seconds before retry',
                            method_id, retry_wait)
                time.sleep(retry_wait)
        else:
            raise Exception('save failed after %d attempts' % max_tries)

    @staticmethod
    def prune_dwdpollens(dbm, method_id, ts, max_tries=3, retry_wait=10):
        """remove dwdpollens older than ts from the database"""

        sql = "delete from %s where method = '%s' and dateTime < %d" % (
            dbm.table_name, method_id, ts)
        for count in range(max_tries):
            try:
                log.debug('%s: deleting dwdpollens prior to %d', method_id, ts)
                dbm.getSql(sql)
                log.info('%s: deleted dwdpollens prior to %d', method_id, ts)
                break
            except weedb.DatabaseError as e:
                log.error('%s: prune failed (attempt %d of %d): %s',
                             method_id, (count + 1), max_tries, e)
                log.debug('%s: waiting %d seconds before retry',
                             method_id, retry_wait)
                time.sleep(retry_wait)
        else:
            raise Exception('prune failed after %d attemps' % max_tries)

    @staticmethod
    def vacuum_database(dbm, method_id):
        # vacuum will only work on sqlite databases.  it will compact the
        # database file.  if we do not do this, the file grows even though
        # we prune records from the database.  it should be ok to run this
        # on a mysql database - it will silently fail.
        try:
            log.debug('%s: vacuuming the database', method_id)
            dbm.getSql('vacuum')
        except weedb.DatabaseError as e:
            log.debug('%s: vacuuming failed: %s', method_id, e)

    # this method is used only by the unit tests
    @staticmethod
    def get_saved_dwdpollens(dbm, method_id, since_ts=None):
        """return saved dwdpollens since the indicated timestamp

        since_ts - timestamp, in seconds.  a value of None will return all.
        """
        sql = "select * from %s where method = '%s'" % (
            dbm.table_name, method_id)
        if since_ts is not None:
            sql += " and dateTime > %d" % since_ts
        records = []
        for r in dbm.genSql(sql):
            records.append(r)
        return records


# -----------------------------------------------------------------------------
#
# DWD Pollen Monitor by DWD
#
# -----------------------------------------------------------------------------

Z_KEY = 'Pollen'

class DWD(DWDPollen):
    """get Pollen from DWD"""

    def __init__(self, engine, config_dict):
        super(DWD, self).__init__(engine, config_dict, Z_KEY,
                                                interval=600)
        d = config_dict.get('DWDPollen', {}).get(Z_KEY, {})
        # keep track of the last time for which we issued a dwdpollen
        self.last_event_ts = 0
        log.info('%s: interval=%s max_age=%s',
                   Z_KEY, self.interval, self.max_age)
        self._bind()

    def get_dwdpollen(self, event):
        """Generate a Pollen from DWD using data from 11:00 (39200 12=43200s).  If the
        current time is before 11:00, use the data from the previous day."""
        now = event.record['dateTime']
        ts = weeutil.weeutil.startOfDay(now) + 43300
        if now < ts:
            ts -= 86400
        if self.last_event_ts == ts:
            log.debug('DWDPollen: Pollen was already calculated for %s',
                       weeutil.weeutil.timestamp_to_string(ts))
            return None

        log.debug('DWDPollen: generating Pollen for %s',
                    weeutil.weeutil.timestamp_to_string(ts))

        dwd_file = "/home/weewx/archive/s31fg.json"
        dwd_url = 'https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json'

        log.info("Pollen-Forecast: NEW  Data dy DWD in %.2f ", ts)

        #Daten from opendata 'DWD' download
        req = urllib2.Request(dwd_url)
        opener = urllib2.build_opener()
        f = opener.open(req)
        data = json.loads(f.read())

        t1 = time.time()

        #with open(dwd_file, "r" ) as read_file:
        #    data = json.load( read_file )

        last_up = data['last_update']
        last_date = last_up
        next_up = data['next_update']
        next_date = next_up

        last_date = re.sub(' Uhr$', '', last_date)
        format = '%Y-%m-%d %H:%M'
        las_up = time.mktime(datetime.datetime.strptime(last_date, format).timetuple())
        log.info("Uhr: LAST Generated in %.2f seconds", las_up)

        next_date = re.sub(' Uhr$', '', next_date)
        format = '%Y-%m-%d %H:%M'
        new_up = time.mktime(datetime.datetime.strptime(next_date, format).timetuple())
        log.info("Uhr: NEW  Generated in %.2f seconds", new_up)

        self.last_event_ts = ts

        record = {}

        record['method'] = Z_KEY
        record['dateTime'] = now
        record['usUnits'] = weewx.METRIC
        record['issued_ts'] = now
        record['event_ts'] = ts
        record['duration'] = 43210
        record['up_date'] = int(las_up)
        record['next_date'] = int(new_up)

        for obj in data['content']:
            heo = DWDPollen.str2int('region_id', obj['region_id'], Z_KEY)
            if heo == 20:
                record['region_id'] = obj['region_id']
                record['region'] = obj['region_name']
                record['hasel_h'] = obj['Pollen']['Hasel']['today']
                record['hasel_m'] = obj['Pollen']['Hasel']['tomorrow']
                record['hasel_n'] = obj['Pollen']['Hasel']['dayafter_to']
                record['erle_h'] = obj['Pollen']['Erle']['today']
                record['erle_m'] = obj['Pollen']['Erle']['tomorrow']
                record['erle_n'] = obj['Pollen']['Erle']['dayafter_to']
                record['birke_h'] = obj['Pollen']['Birke']['today']
                record['birke_m'] = obj['Pollen']['Birke']['tomorrow']
                record['birke_n'] = obj['Pollen']['Birke']['dayafter_to']
                record['graeser_h'] = obj['Pollen']['Graeser']['today']
                record['graeser_m'] = obj['Pollen']['Graeser']['tomorrow']
                record['graeser_n'] = obj['Pollen']['Graeser']['dayafter_to']
                record['roggen_h'] = obj['Pollen']['Roggen']['today']
                record['roggen_m'] = obj['Pollen']['Roggen']['tomorrow']
                record['roggen_n'] = obj['Pollen']['Roggen']['dayafter_to']
                record['esche_h'] = obj['Pollen']['Esche']['today']
                record['esche_m'] = obj['Pollen']['Esche']['tomorrow']
                record['esche_n'] = obj['Pollen']['Esche']['dayafter_to']
                record['beifuss_h'] = obj['Pollen']['Beifuss']['today']
                record['beifuss_m'] = obj['Pollen']['Beifuss']['tomorrow']
                record['beifuss_n'] = obj['Pollen']['Beifuss']['dayafter_to']
                record['ambrosia_h'] = obj['Pollen']['Ambrosia']['today']
                record['ambrosia_m'] = obj['Pollen']['Ambrosia']['tomorrow']
                record['ambrosia_n'] = obj['Pollen']['Ambrosia']['dayafter_to']


        t2 = time.time()

        log.info("Pollen: Generated in %.2f seconds", t2 - t1)

        log.info('%s: generated 1 forecast record', Z_KEY)

        return record

