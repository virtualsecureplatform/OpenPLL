"""Permit only OpenDB's non-geometric SPECIAL annotation on the two PG pins."""
import re


def normalized_pg_metadata(text):
    pattern=re.compile(r'(?m)^([ \t]*-[ \t]+(VPWR|VGND)[ \t]+\+[ \t]+NET[ \t]+\2)'
                       r'([ \t]+\+[ \t]+SPECIAL)?'
                       r'(?=[ \t]+\+[ \t]+DIRECTION[ \t]+INOUT[ \t]+\+[ \t]+USE[ \t]+(POWER|GROUND)\b)')
    def normalize(match):
        if match[4]!={'VPWR':'POWER','VGND':'GROUND'}[match[2]]:
            raise ValueError('power pin use does not match its named rail')
        return match[1]
    return pattern.sub(normalize,text)


def pin_sections_equivalent(before,after):
    return normalized_pg_metadata(before)==normalized_pg_metadata(after)
