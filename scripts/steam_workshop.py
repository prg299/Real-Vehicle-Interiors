"""Shared metadata/identity helpers for SteamCMD and the native PZ uploader."""
from pathlib import Path
import re

def item_id(value):
    value=str(value or '').strip()
    if value in ('','0'): return None
    if not re.fullmatch(r'[1-9][0-9]*',value):
        raise ValueError('Invalid Workshop item ID')
    return value

def reconcile_ids(*values):
    ids={parsed for value in values if (parsed:=item_id(value)) is not None}
    if len(ids)>1: raise ValueError('Conflicting Workshop IDs; upload stopped to preserve both records.')
    return next(iter(ids),None)

def metadata(path):
    result={}; description=[]
    for line in Path(path).read_text('utf-8-sig').splitlines():
        key,sep,value=line.partition('=')
        if not sep: continue
        if key=='description': description.append(value)
        elif key in result: raise ValueError('Duplicate Workshop metadata key: '+key)
        else: result[key]=value
    result['description']='\n'.join(description)
    return result

def vdf_field(path,key):
    path=Path(path)
    if not path.exists(): return None
    values=re.findall(r'^\s*"'+re.escape(key)+r'"\s+"([^"\r\n]*)"\s*$',path.read_text('utf-8-sig'),re.M|re.I)
    if len(values)!=1: raise ValueError('Missing or ambiguous VDF field: '+key)
    return values[0]

def quote(value):
    value=str(value)
    if '\0' in value: raise ValueError('NUL in VDF value')
    # SteamCMD preserves backslash-n as visible text in Workshop descriptions.
    # KeyValues quoted strings support physical line breaks; retain those.
    value=value.replace('\r\n','\n').replace('\r','\n')
    return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'

def make_vdf(app_id,info,content,preview,published_id=None,changenote=''):
    visibility = info.get('visibility')
    if visibility not in ('unlisted', 'preserve'): raise ValueError('Use unlisted or preserve visibility.')
    if visibility == 'preserve' and not item_id(published_id): raise ValueError('Only an existing item can preserve visibility.')
    fields={'appid':str(app_id),'publishedfileid':item_id(published_id) or '0',
        'contentfolder':Path(content).resolve().as_posix(),'previewfile':Path(preview).resolve().as_posix(),
        **({'visibility':'3'} if visibility == 'unlisted' else {}),
        'title':info['title'],'description':info['description'],
        'changenote':changenote}
    lines=['"workshopitem"','{']
    lines += ['    '+quote(key)+' '+quote(value) for key,value in fields.items()]
    lines += ['    "tags"','    {']
    lines += ['        '+quote(index)+' '+quote(tag) for index,tag in enumerate(info.get('tags','').split(';')) if tag]
    lines += ['    }','}','']
    return '\n'.join(lines)

def retain_id(path,published_id):
    path=Path(path); published_id=item_id(published_id)
    if published_id is None: return
    info=metadata(path)
    reconcile_ids(info.get('id'),published_id)
    lines=[line for line in path.read_text('utf-8-sig').splitlines() if not line.startswith('id=')]
    lines.insert(1,'id='+published_id)
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
