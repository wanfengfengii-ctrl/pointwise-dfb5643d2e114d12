from fractions import Fraction
from .rings import cross

def component_area(component):
    return sum((cross(s.start, s.end) for b in component.boundaries for s in b.segments), Fraction())/2

def coverage_area(geometry):
    return sum((component_area(c) for c in geometry.components), Fraction())

def area_items(geometry):
    result = [{'component_id': c.component_id, 'area': component_area(c)} for c in geometry.components]
    if any(item['area'] <= 0 for item in result):
        raise ValueError('nonpositive component area')
    return result
