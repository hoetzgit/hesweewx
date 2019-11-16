#
#    Copyright (c) 2011 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision: 1459 $
#    $Author: mwall $
#    $Date: 2013-10-08 17:44:50 -0700 (Tue, 08 Oct 2013) $
#
"""Database schemas used by weewx"""

#===============================================================================
# This is a list containing the default schema of the archive database.  It is
# identical to what is used by wview. It is only used for initialization ---
# afterwards, the schema is obtained dynamically from the database.  Although a
# type may be listed here, it may not necessarily be supported by your weather
# station hardware.
#
# You may trim this list of any unused types if you wish, but it will not
# result in saving as much space as you may think --- most of the space is
# taken up by the primary key indexes (type "dateTime").
# =============================================================================
table = [('dateTime',             'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
                        ('usUnits',              'INTEGER NOT NULL'),
                        ('interval',             'INTEGER NOT NULL'),
                        ('barometer',            'REAL'),
                        ('pressure',             'REAL'),
                        ('altimeter',            'REAL'),
                        ('inTemp',               'REAL'),
                        ('outTemp',              'REAL'),
                        ('inHumidity',           'REAL'),
                        ('outHumidity',          'REAL'),
                        ('windSpeed',            'REAL'),
                        ('windDir',              'REAL'),
                        ('windGust',             'REAL'),
                        ('windGustDir',          'REAL'),
                        ('rainRate',             'REAL'),
                        ('rain',                 'REAL'),
                        ('dewpoint',             'REAL'),
                        ('windchill',            'REAL'),
                        ('heatindex',            'REAL'),
                        ('ET',                   'REAL'),
                        ('radiation',            'REAL'),
                        ('UV',                   'REAL'),
                        ('extraTemp1',           'REAL'),
                        ('extraTemp2',           'REAL'),
                        ('extraTemp3',           'REAL'),
                        ('extraTemp4',           'REAL'),
                        ('extraTemp5',           'REAL'),
                        ('extraTemp6',           'REAL'),
                        ('extraTemp7',           'REAL'),
                        ('extraTemp8',           'REAL'),
                        ('extraTemp9',           'REAL'),
                        ('extraTemp10',           'REAL'),
                        ('extraTemp11',           'REAL'),
                        ('extraTemp12',           'REAL'),
                        ('extraTemp13',           'REAL'),
                        ('extraTemp14',           'REAL'),
                        ('extraTemp15',           'REAL'),
                        ('extraTemp16',           'REAL'),
                        ('extraTemp17',           'REAL'),
                        ('extraTemp18',           'REAL'),
                        ('extraTemp19',           'REAL'),
                        ('extraTemp20',           'REAL'),
                        ('extraTemp21',           'REAL'),
                        ('extraTemp22',           'REAL'),
                        ('extraTemp23',           'REAL'),
                        ('extraTemp24',           'REAL'),
                        ('soilTemp1',            'REAL'),
                        ('soilTemp2',            'REAL'),
                        ('soilTemp3',            'REAL'),
                        ('soilTemp4',            'REAL'),
                        ('soilTemp5',            'REAL'),
                        ('leafTemp1',            'REAL'),
                        ('leafTemp2',            'REAL'),
                        ('extraHumid1',          'REAL'),
                        ('extraHumid2',          'REAL'),
                        ('soilMoist1',           'REAL'),
                        ('soilMoist2',           'REAL'),
                        ('soilMoist3',           'REAL'),
                        ('soilMoist4',           'REAL'),
                        ('leafWet1',             'REAL'),
                        ('leafWet2',             'REAL'),
                        ('rxCheckPercent',       'REAL'),
                        ('txBatteryStatus',      'REAL'),
                        ('consBatteryVoltage',   'REAL'),
                        ('hail',                 'REAL'),
                        ('hailRate',             'REAL'),
                        ('heatingTemp',          'REAL'),
                        ('heatingVoltage',       'REAL'),
                        ('supplyVoltage',        'REAL'),
                        ('referenceVoltage',     'REAL'),
                        ('windBatteryStatus',    'REAL'),
                        ('rainBatteryStatus',    'REAL'),
                        ('outTempBatteryStatus', 'REAL'),
                        ('lighting',             'REAL'),
                        ('lightning',            'REAL'),
                        ('inTempBatteryStatus',  'REAL'),
                        ('gas',                  'REAL'),
                        ('gasTotal',             'REAL'),
                        ('gasZahl',              'REAL'),
                        ('ele',                  'REAL'),
                        ('eleTotal',             'REAL'),
                        ('eleZahl',              'REAL'),
                        ('eleA',                 'REAL'),
                        ('eleATotal',            'REAL'),
                        ('eleAZahl',             'REAL'),
                        ('was',                  'REAL'),
                        ('wasTotal',             'REAL'),
                        ('wasZahl',              'REAL'),
                        ('wasA',                 'REAL'),
                        ('wasATotal',            'REAL'),
                        ('wasAZahl',             'REAL'),
                        ('snow',                 'REAL'),
                        ('snowRate',             'REAL'),
                        ('snowTotal',            'REAL'),
                        ('maxSolarRad',          'REAL'),
                        ('cloudbase',            'REAL'),
                        ('humidex',              'REAL'),
                        ('appTemp',              'REAL'),
                        ('windrun',              'REAL'),
                        ('beaufort',             'REAL'),
                        ('inDewpoint',           'REAL'),
                        ('absolutF',             'REAL'),
                        ('wetBulb',              'REAL'),
                        ('cbIndex',              'REAL'),
                        ('windDruck',            'REAL'),
                        ('sunshineS',            'REAL'),
                        ('airDensity',           'REAL'),
                        ('da_altitude',          'REAL'),
]

# Schema to be used for the daily summaries. The default is to include all the observation types in the table as
# 'scalar' types, plus one for 'wind' as a vector type.
day_summaries = [(e[0], 'scalar') for e in table if e[0] not in ('dateTime', 'usUnits', 'interval')]\
                + [('wind', 'vector')]

schema = {
    'table': table,
    'day_summaries' : day_summaries
}
