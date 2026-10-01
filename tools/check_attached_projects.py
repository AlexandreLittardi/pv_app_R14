"""Verify supplied project migrations and geometry without touching their files."""
import copy
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from project_store import validate_project,write_project
from mixins.installation_geometry import InstallationGeometryMixin
from mixins.shadow_geometry import ShadowGeometryMixin
from mixins.spreadsheet_tools import SpreadsheetToolsMixin
import tempfile

class Geometry(InstallationGeometryMixin,ShadowGeometryMixin):pass

result={}
for path in sorted((Path(__file__).resolve().parents[1]/'exemples_joints').glob('*.json')):
    raw=path.read_bytes();original=json.loads(raw);data=validate_project(original)
    g=Geometry()
    for key in ('px_per_mm','panel_width_mm','panel_height_mm','roof_zones','model_settings'):setattr(g,key,copy.deepcopy(data[key]))
    g.panels={tuple(map(int,k.split(','))):v for k,v in data['panels'].items()}
    g.strings={sid:[tuple(map(int,k.split(','))) for k in coords] for sid,coords in data['strings'].items()}
    g._recalculate_zone_grids();issues=g._layout_issues()
    assert not issues,issues
    variables=SpreadsheetToolsMixin._get_zone_string_insert_vars(g)
    count=sum(value for key,value in variables.items() if key.startswith('ZONE') and key.endswith('PANEL_COUNT'))
    assert count==len(g.panels),(count,len(g.panels))
    with tempfile.TemporaryDirectory() as folder:
        output=Path(folder)/path.name;write_project(output,data)
        reread=validate_project(json.loads(output.read_text()))
        assert reread['panels']==original['panels']
        assert reread['strings']==original['strings']
    assert path.read_bytes()==raw
    result[path.name]={'panels':len(g.panels),'zones':len(g.roof_zones),'layout_issues':len(issues),
        'zone_formula_panel_count':count,'source_sha256':hashlib.sha256(raw).hexdigest(),
        'source_unchanged':True,'json_roundtrip':'passed'}
print(json.dumps(result,ensure_ascii=False,indent=2))
