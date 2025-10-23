"""
Dice Rolling Chart Data

Contains all chart dictionaries for baseball dice rolling mechanics.
Extracted from rolls.py for better maintainability.
"""

# ============================================================================
# X-CHART DATA
# ============================================================================

INFIELD_X_CHART = {
    'si1': {
        'rp': 'Runner on first: Line drive hits the runner! Runner on first is out. Batter goes to first with single '
              'and all other runners hold.\nNo runner on first: batter singles, runners advance 1 base.',
        'e1': 'Single and Error, batter to second, runners advance 2 bases.',
        'e2': 'Single and Error, batter to third, all runners score.',
        'no': 'Single, runners advance 1 base.'
    },
    'spd': {
        'rp': 'No effect; proceed with speed check',
        'e1': 'Single and Error, batter to second, runners advance 2 bases.',
        'e2': 'Single and Error, batter to third, all runners score.',
        'no': 'Speed check, safe range equals batter\'s running rating, SI* result if safe, gb C if out'
    },
    'po': {
        'rp': 'The batters hits a popup. None of the fielders take charge on the play and the ball drops in the '
              'infield for a single! All runners advance 1 base.',
        'e1': 'The catcher drops a popup for an error. All runners advance 1 base.',
        'e2': 'The catcher grabs a squib in front of the plate and throws it into right field. The batter goes to '
              'second and all runners score.',
        'no': 'The batter pops out to the catcher.'
    },
    'wp': {
        'rp': 'Automatic wild pitch. Catcher has trouble finding it and all base runners advance 2 bases.',
        'no': 'Automatic wild pitch, all runners advance 1 base and batter rolls AB again.'
    },
    'x': {
        'rp': 'Runner(s) on base: pitcher trips during his delivery and the ball sails for automatic wild pitch, '
              'runners advance 1 base and batter rolls AB again.',
        'no': 'Wild pitch check (credited as a PB). If a passed ball occurs, batter rerolls AB. '
              'If no passed ball occurs, the batter fouls out to the catcher.'
    },
    'fo': {
        'rp': 'Batter swings and misses, but is awarded first base on a catcher interference call! Baserunners advance '
              'only if forced.',
        'e1': 'The catcher drops a foul popup for an error. Batter rolls AB again.',
        'e2': 'The catcher drops a foul popup for an error. Batter rolls AB again.',
        'no': 'Runner(s) on base: make a passed ball check. If no passed ball, batter pops out to the catcher. If a '
              'passed ball occurs, batter roll his AB again.\nNo runners: batter pops out to the catcher'
    },
    'g1': {
        'rp': 'Runner on first: runner on first breaks up the double play, but umpires call runner interference and '
              'the batter is out on GIDP.\nNo runners: Batter grounds out.',
        'e1': 'Error, batter to first, runners advance 1 base.',
        'e2': 'Error, batter to second, runners advance 2 bases.',
        'no': 'Consult Groundball Chart: `!gbA`'
    },
    'g2': {
        'rp': 'Batter lines the ball off the pitcher to the fielder who makes the play to first for the out! Runners '
              'advance only if forced.',
        'e1': 'Error, batter to first, runners advance 1 base.',
        'e2': 'Error, batter to second, runners advance 2 bases.',
        'no': 'Consult Groundball Chart: `!gbB`'
    },
    'g3': {
        'rp': 'Batter lines the ball off the mound and deflects to the fielder who makes the play to first for the '
              'out! Runners advance 1 base.',
        'e1': 'Error, batter to first, runners advance 1 base.',
        'e2': 'Error, batter to second, runners advance 2 bases.',
        'no': 'Consult Groundball Chart: `!gbC`'
    },
}

OUTFIELD_X_CHART = {
    'si2': {
        'rp': 'Batter singles, baserunners advance 2 bases. As the batter rounds first, the fielder throws behind him '
              'and catches him off the bag for an out!',
        'e1': 'Single and error, batter to second, runners advance 2 bases.',
        'e2': 'Single and error, batter to third, all runners score.',
        'e3': 'Single and error, batter to third, all runners score',
        'no': 'Single, all runners advance 2 bases.'
    },
    'do2': {
        'rp': 'Batter doubles, runners advance 2 bases. The outfielder throws the ball to the shortstop who executes a '
              'hidden ball trick! Runner on second is called out!',
        'e1': 'Double and error, batter to third, all runners score.',
        'e2': 'Double and error, batter to third, and all runners score.',
        'e3': 'Double and error, batter and all runners score. Little league home run!',
        'no': 'Double, all runners advance 2 bases.'
    },
    'do3': {
        'rp': 'Runner(s) on base: batter doubles and runners advance three bases as the outfielders collide!\n'
              'No runners: Batter doubles, but the play is appealed. The umps rule the batter missed first base so is '
              'out on the appeal!',
        'e1': 'Double and error, batter to third, all runners score.',
        'e2': 'Double and error, batter and all runners score. Little league home run!',
        'e3': 'Double and error, batter and all runners score. Little league home run!',
        'no': 'Double, all runners score.'
    },
    'tr3': {
        'rp': 'Batter hits a ball into the gap and the outfielders collide trying to make the play! The ball rolls to '
              'the wall and the batter trots home with an inside-the-park home run!',
        'e1': 'Triple and error, batter and all runners score. Little league home run!',
        'e2': 'Triple and error, batter and all runners score. Little league home run!',
        'e3': 'Triple and error, batter and all runners score. Little league home run!',
        'no': 'Triple, all runners score.'
    },
    'f1': {
        'rp': 'The outfielder races back and makes a diving catch and collides with the wall! In the time he takes to '
              'recuperate, all baserunners tag-up and advance 2 bases.',
        'e1': '1 base error, runners advance 1 base.',
        'e2': '2 base error, runners advance 2 bases.',
        'e3': '3 base error, batter to third, all runners score.',
        'no': 'Flyball A'
    },
    'f2': {
        'rp': 'The outfielder catches the flyball for an out. If there is a runner on third, he tags-up and scores. '
              'The play is appealed and the umps rule that the runner left early and is out on the appeal!',
        'e1': '1 base error, runners advance 1 base.',
        'e2': '2 base error, runners advance 2 bases.',
        'e3': '3 base error, batter to third, all runners score.',
        'no': 'Flyball B'
    },
    'f3': {
        'rp': 'The outfielder makes a running catch in the gap! The lead runner lost track of the ball and was '
              'advancing - he cannot return in time and is doubled off by the outfielder.',
        'e1': '1 base error, runners advance 1 base.',
        'e2': '2 base error, runners advance 2 bases.',
        'e3': '3 base error, batter to third, all runners score.',
        'no': 'Flyball C'
    }
}

# ============================================================================
# FIELDING RANGE CHARTS
# ============================================================================

INFIELD_RANGES = {
    1: 'G3# SI1 ----SI2----',
    2: 'G2# SI1 ----SI2----',
    3: 'G2# G3# SI1 --SI2--',
    4: 'G2# G3# SI1 --SI2--',
    5: 'G1  --G3#-- SI1 SI2',
    6: 'G1  G2# G3# SI1 SI2',
    7: 'G1  G2  --G3#-- SI1',
    8: 'G1  G2  --G3#-- SI1',
    9: 'G1  G2  G3  --G3#--',
    10: '--G1--- G2  --G3#--',
    11: '--G1--- G2  G3  G3#',
    12: '--G1--- G2  G3  G3#',
    13: '--G1--- G2  --G3---',
    14: '--G1--- --G2--- G3',
    15: '----G1----- G2  G3',
    16: '----G1----- G2  G3',
    17: '------G1------- G3',
    18: '------G1------- G2',
    19: '------G1------- G2',
    20: '--------G1---------'
}

OUTFIELD_RANGES = {
    1: 'F1  DO2 DO3 --TR3--',
    2: 'F2  SI2 DO2 DO3 TR3',
    3: 'F2  SI2 --DO2-- DO3',
    4: 'F2  F1  SI2 DO2 DO3',
    5: '--F2--- --SI2-- DO2',
    6: '--F2--- --SI2-- DO2',
    7: '--F2--- F1  SI2 DO2',
    8: '--F2--- F1  --SI2--',
    9: '----F2----- --SI2--',
    10: '----F2----- --SI2--',
    11: '----F2----- --SI2--',
    12: '----F2----- F1  SI2',
    13: '----F2----- F1  SI2',
    14: 'F3  ----F2----- SI2',
    15: 'F3  ----F2----- SI2',
    16: '--F3--- --F2--- F1',
    17: '----F3----- F2  F1',
    18: '----F3----- F2  F1',
    19: '------F3------- F2',
    20: '--------F3---------'
}

CATCHER_RANGES = {
    1: 'G3  ------SI1------',
    2: 'G3  SPD ----SI1----',
    3: '--G3--- SPD --SI1--',
    4: 'G2  G3  --SPD-- SI1',
    5: 'G2  --G3--- --SPD--',
    6: '--G2--- G3  --SPD--',
    7: 'PO  G2  G3  --SPD--',
    8: 'PO  --G2--- G3  SPD',
    9: '--PO--- G2  G3  SPD',
    10: 'FO  PO  G2  G3  SPD',
    11: 'FO  --PO--- G2  G3',
    12: '--FO--- PO  G2  G3',
    13: 'G1  FO  PO  G2  G3',
    14: 'G1  --FO--- PO  G2',
    15: '--G1--- FO  PO  G2',
    16: '--G1--- FO  PO  G2',
    17: '----G1----- FO  PO',
    18: '----G1----- FO  PO',
    19: '----G1----- --FO---',
    20: '------G1------- FO'
}

PITCHER_RANGES = {
    1: 'G3  ------SI1------',
    2: 'G3  ------SI1------',
    3: '--G3--- ----SI1----',
    4: '----G3----- --SI1--',
    5: '------G3------- SI1',
    6: '------G3------- SI1',
    7: '--------G3---------',
    8: 'G2  ------G3-------',
    9: 'G2  ------G3-------',
    10: 'G1  G2  ----G3-----',
    11: 'G1  G2  ----G3-----',
    12: 'G1  G2  ----G3-----',
    13: '--G1--- G2  --G3---',
    14: '--G1--- --G2--- G3',
    15: '--G1--- ----G2-----',
    16: '--G1--- ----G2-----',
    17: '----G1----- --G2---',
    18: '----G1----- --G2---',
    19: '------G1------- G2',
    20: '--------G1---------'
}

# ============================================================================
# ERROR CHARTS
# ============================================================================

FIRST_BASE_ERRORS = {
    18: '2-base error for e3 -> e12, e19 -> e28\n1-base error for e1, e2, e30',
    17: '2-base error for e13 -> e28\n1-base error for e1, e5, e8, e9, e29',
    16: '2-base error for e29, e30\n1-base error for e2, e8, e16, e19, e23',
    15: '1-base error for e3, e8, e10 -> e12, e20, e26, e30',
    14: '1-base error for e4, e5, e9, e15, e18, e22, e24 -> e28',
    13: '1-base error for e6, e13, e24, e26 -> e28, e30',
    12: '1-base error for e14 -> e18, e21 -> e26, e28 -> e30',
    11: '1-base error for e10, e13, e16 -> e20, e23 -> e25, e27 -> e30',
    10: '1-base error for e19 -> e21, e23, e29',
    9: '1-base error for e7, e12, e14, e21, e25, e26, e29',
    8: '1-base error for e11, e27',
    7: '1-base error for e9, e15, e22, e27, e28',
    6: '1-base error for e8, e11, e12, e17, e20',
    5: 'No error',
    4: 'No error',
    3: '2-base error for e8 -> e12, e24 -> e28\n1-base error for e2, e3, e6, e7, e14, e16, e17, e21'
}

SECOND_BASE_ERRORS = {
    18: '2-base error for e4 -> e19, e28 -> e41, e53 -> e65\n1-base error for e22, e24, e25, e27, e44, e50',
    17: '2-base error for e20 -> e41, e68, e71\n1-base error for e3, e4, e8 -> e12, e15, e16, e19',
    16: '2-base error for e53 -> 71\n1-base error for e5 -> 10, e14, e16, e29, e37',
    15: '1-base error for e11, e12, e14, e16, e17, e19, e26 -> e28, e30, e32, e37, e50 -> e62, e71',
    14: '1-base error for e13, e15, e34, e47, e65',
    13: '1-base error for e18, e20, e21, e26 -> e28, e39, e41, e50, e56, e59, e65, e71',
    12: '1-base error for e22, e30, e34, e39, e44, e47, e53, e56, e62, e68, e71',
    11: '1-base error for e23 -> e25, e29, e32, e37, e41, e50, e53, e59, e62, e68',
    10: '1-base error for e68',
    9: '1-base error for e44',
    8: 'No error',
    7: '1-base error for e47, e65',
    6: '1-base error for e17, e19, e56 -> 62',
    5: 'No error',
    4: '1-base error for e10, e21',
    3: '2-base error for e12 -> e19, e37 -> e41, e59 -> e65\n1-base error for e2 -> e4, e6, e20, e25, e28, e29'
}

THIRD_BASE_ERRORS = {
    18: '2-base error for e11 -> e18, e32, e33, e37, e53, e62, e65\n1-base error for e4, e8, e19, e21, e22, e27, e41',
    17: '2-base error for e3 -> e10, e17, e18, e25 -> e27, e34 -> e37, e44, e47\n1-base error for e11, e19, e32, e56',
    16: '2-base error for e11 -> e18, e32, e33, e37, e53, e62, e65\n1-base error for e4, e8, e19, e21, e22, e27, e41',
    15: '2-base error for e19 -> 27, e32, e33, e37, e39, e44, e50, e59\n1-base error for e5 -> e8, e11, e14, e15, e17, e18, e28 -> e31, e34',
    14: '2-base error for e28 -> e31, e34, e35, e50\n1-base error for e14, e16, e19, e20, e22, e32, e39, e44, e56, e62',
    13: '2-base error for e41, e47, e53, e59\n1-base error for e10, e15, e23, e25, e28, e30, e32, e33, e35, e44, e65',
    12: '2-base error for e62\n1-base error for e12, e17, e22, e24, e27, e29, e34 -> e50, e56 -> e59, e65',
    11: '2-base error for e56, e65\n1-base error for e13, e18, e20, e21, e23, e26, e28, e31 -> e33, e35, e37, e41 -> e53, e59',
    10: '1-base error for e26, e31, e41, e53 -> 65',
    9: '1-base error for e24, e27, e29, e34, e37, e39, e47 -> e65',
    8: '1-base error for e25, e30, e33, e47, e53, e56, e62, e65',
    7: '1-base error for e16, e19, e39, e59 -> e65',
    6: '1-base error for e21, e25, e30, e34, e53',
    5: 'No error',
    4: '1-base error for e2, e3, e6, e14, e16, e44',
    3: '2-base error for e10, e15, e16, e23, e24, e56\n1-base error for e1 -> e4, e8, e14'
}

SHORTSTOP_ERRORS = {
    18: '2-base error for e4 -> e12, e22 -> e32, e40 -> e48, e64, e68\n1-base error for e1, e18, e34, e52, e56',
    17: '2-base error for e14 -> 32, e52, e56, e72 -> e84\n1-base error for e3 -> e5, e8 ,e10, e36',
    16: '2-base error for e33 -> 56, e72\n1-base error for e6 -> e10, e17, e18, e20, e28, e31, e88',
    15: '2-base error for e60 -> e68, e76 -> 84\n1-base error for e12, e14, e17, e18, e20 -> e22, e24, e28, e31 -> 36, e40, e48, e72',
    14: '1-base error for e16, e19, e38, e42, e60, e68',
    13: '1-base error for e23, e25, e32 -> 38, e44, e52, e72 -> 84',
    12: '1-base error for e26, e27, e30, e42, e48, e56, e64, e68, e76 -> e88',
    11: '1-base error for e29, e40, e52 -> e60, e72, e80 -> e88',
    10: '1-base error for e84',
    9: '1-base error for e64, e68, e76, e88',
    8: '1-base error for e44',
    7: '1-base error for e60',
    6: '1-base error for e21, e22, e24, e28, e31, e48, e64, e72',
    5: 'No error',
    4: '2-base error for e72\n1-base error for e14, e19, e20, e24, e25, e30, e31, e80',
    3: '2-base error for e10, e12, e28 -> e32, e48, e84\n1-base error for e2, e5, e7, e23, e27'
}

CORNER_OUTFIELD_ERRORS = {
    18: '3-base error for e4 -> e12, e19 -> e25\n2-base error for e18\n1-base error for e2, e3, e15',
    17: '3-base error for e13 -> e25\n2-base error for e1, e6, e8, e10',
    16: '2-base error for e2\n1-base error for e7 -> 12, e22, e24, e25',
    15: '2-base error for e3, e4, e7, e8, e10, e11, e13, e20, e21',
    14: '2-base error for e5, e6, e10, e12, e14, e15, e22, e23',
    13: '2-base error for e11, e12, e16, e20, e24, e25',
    12: '2-base error for e13 -> e18, e21 -> e23, e25',
    11: '2-base error for e9, e18 -> e21, e23 -> e25',
    10: '2-base error for e19',
    9: '2-base error for e22',
    8: '2-base error for e24',
    7: '1-base error for e19 -> e21, e23',
    6: '2-base error for e7, e8\n1-base error for e13 -> e18, e22, e24, e25',
    5: 'No error',
    4: '2-base error for e1, e5, e6, e9\n1-base error for e14 -> e16, e20 -> e23',
    3: '3-base error for e16 -> e25\n2-base error for e1, e3, e4, e7, e9, e11\n1-base error for e17'
}

CENTER_FIELD_ERRORS = {
    18: '3-base error for e4 -> e19\n2-base error for e2, e25\n1-base error for e3, e23',
    17: '3-base error for e20 -> e25\n2-base error for e1, e2, e5, e7, e9, e13 -> e15, e17',
    16: '2-base error for e3 -> e5, e8, e23\n1-base error for e10 -> e18',
    15: '2-base error for e6 -> e8, e12, e13, e19',
    14: '2-base error for e9, e10, e16 -> e18, e20 -> e23',
    13: '2-base error for e11, e18, e20, e23 -> e25',
    12: '2-base error for e14, e15, e21, e22, e24',
    11: '2-base error for e19, e25',
    10: 'No error',
    9: 'No error',
    8: 'No error',
    7: '2-base error for e16, e17',
    6: '2-base error for e12, e13\n1-base error for e19 -> e25',
    5: 'No error',
    4: '2-base error for e10, e12, e13, e20, e22, e23\n1-base error for e3 -> e9, e15 -> e18',
    3: '3-base error for e12 -> e19\n2-base error for e10, e11\n1-base error for e2, e3, e7 -> e9, e21 -> e23'
}

CATCHER_ERRORS = {
    18: '2-base error for e4 -> 16\n1-base error for e2, e3',
    17: '1-base error for e1, e2, e4, e5, e12 -> e14, e16',
    16: '1-base error for e3 -> e5, e7, e12 -> e14, e16',
    15: '1-base error for e7, e8, e12, e13, e15',
    14: '1-base error for e6',
    13: '1-base error for e9',
    12: '1-base error for e10, e14',
    11: '1-base error for e11, e15',
    10: 'No error',
    9: 'No error',
    8: 'No error',
    7: '1-base error for e16',
    6: '1-base error for e8, e12, e13',
    5: 'No error',
    4: '1-base error for e5, e13',
    3: '2-base error for e12 -> e16\n1-base error for e2, e3, e7, e11'
}

PITCHER_ERRORS = {
    18: '2-base error for e4 -> e12, e19 -> e28, e34 -> e43, e46 -> e48',
    17: '2-base error for e13 -> e28, e44 -> e50',
    16: '2-base error for e30 -> e48, e50, e51\n1-base error for e8, e11, e16, e23',
    15: '2-base error for e50, e51\n1-base error for e10 -> e12, e19, e20, e24, e26, e30, e35, e38, e40, e46, e47',
    14: '1-base error for e4, e14, e18, e21, e22, e26, e31, e35, e42, e43, e48 -> e51',
    13: '1-base error for e6, e13, e14, e21, e22, e26, e27, e30 -> 34, e38 -> e51',
    12: '1-base error for e7, e11, e12, e15 -> e19, e22 -> e51',
    11: '1-base error for e10, e13, e15, e17, e18, e20, e21, e23, e24, e27 -> 38, e40, e42, e44 -> e51',
    10: '1-base error for e20, e23, e24, e27 -> e51',
    9: '1-base error for e16, e19, e26, e28, e34 -> e36, e39 -> e51',
    8: '1-base error for e22, e33, e38, e39, e43 -> e51',
    7: '1-base error for e14, e21, e36, e39, e42 -> e44, e47 -> e51',
    6: '1-base error for e8, e22, e38, e39, e43 -> e51',
    5: 'No error',
    4: '1-base error for e15, e16, e40',
    3: '2-base error for e8 -> e12, e26 -> e28, e39 -> e43\n1-base error for e2, e3, e7, e14, e15'
}
