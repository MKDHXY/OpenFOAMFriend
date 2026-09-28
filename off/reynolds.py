"""SI Reynolds scaling. Pure helpers never edit geometry or solver dictionaries."""
import math

def positive(value, name):
    value=float(value)
    if not math.isfinite(value) or value<=0: raise ValueError(name+' must be finite and positive.')
    return value

def reference(project):
    if project.reference_length>0: return project.reference_length, 'custom'
    if project.mesh_method.startswith('Manual topology'):
        raise ValueError('Manual topology requires an explicit flow reference length; original automatic solids are retained but are not the manual geometry.')
    if len(project.shapes)==1:
        shape=project.shapes[0]
        return positive(shape['width'],'Obstacle width'), 'diameter' if shape['kind']=='circle' and abs(shape['width']-shape['height'])<1e-12 else 'width'
    raise ValueError('Choose an explicit reference length for multiple obstacles or an empty domain.')

def reynolds(u,length,nu):
    value=positive(u,'U')*positive(length,'L')/positive(nu,'nu')
    return positive(value,'Re')

def solve(target,u,length,nu,variable):
    target=positive(target,'Re'); u=positive(u,'U'); length=positive(length,'L'); nu=positive(nu,'nu')
    if not 1<=target<=1e7: raise ValueError('The target-Re control covers 1 to 10,000,000.')
    if variable=='viscosity': return positive(u*length/target,'nu')
    if variable=='velocity': return positive(target*nu/length,'U')
    raise ValueError('Only velocity or viscosity may be solved; geometry is never rescaled.')
