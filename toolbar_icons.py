"""Original monochrome line icons, drawn from geometric primitives (no glyphs)."""
import re
import unicodedata
from PIL import Image,ImageDraw,ImageTk

# Primitives use a 24-unit design grid: line, rectangle, ellipse, polygon.
ICONS={
 'folder':[('l',[(3,19),(3,6),(10,6),(12,9),(21,9),(19,19),(3,19)])],
 'settings':[('l',[(4,6),(20,6)]),('l',[(4,12),(20,12)]),('l',[(4,18),(20,18)]),('r',(8,4,11,8)),('r',(15,10,18,14)),('r',(6,16,9,20))],
 'pdf':[('l',[(6,21),(6,3),(15,3),(19,7),(19,21),(6,21)]),('l',[(14,3),(14,8),(19,8)]),('l',[(9,12),(16,12)]),('l',[(9,16),(16,16)])],
 'ruler':[('r',(3,7,21,17)),('l',[(7,7),(7,12)]),('l',[(11,7),(11,10)]),('l',[(15,7),(15,12)]),('l',[(19,7),(19,10)])],
 'polygon':[('l',[(4,17),(7,4),(19,7),(21,18),(4,17)]),('r',(5,2,9,6)),('r',(17,5,21,9))],
 'zones':[('r',(3,4,14,16)),('r',(10,10,21,21))],
 'panel':[('r',(4,3,20,19)),('l',[(12,3),(12,19)]),('l',[(4,11),(20,11)]),('l',[(8,22),(16,22)]),('l',[(12,19),(12,22)])],
 'grid':[('r',(3,3,21,21)),('l',[(9,3),(9,21)]),('l',[(15,3),(15,21)]),('l',[(3,9),(21,9)]),('l',[(3,15),(21,15)])],
 'string':[('r',(2,7,7,14)),('r',(10,7,15,14)),('r',(18,7,23,14)),('l',[(7,11),(10,11)]),('l',[(15,11),(18,11)])],
 'inverter':[('r',(5,3,19,21)),('l',[(8,9),(10,7),(14,11),(16,9)]),('l',[(8,16),(16,16)]),('l',[(8,18),(16,18)])],
 'diagram':[('r',(2,3,8,8)),('r',(2,16,8,21)),('r',(16,9,22,15)),('l',[(8,5),(12,5),(12,19),(8,19)]),('l',[(12,12),(16,12)])],
 'link':[('l',[(8,16),(5,19),(2,16),(7,11),(10,14)]),('l',[(14,10),(11,7),(16,2),(19,5),(16,8)]),('l',[(8,16),(16,8)])],
 'plus':[('l',[(4,12),(20,12)]),('l',[(12,4),(12,20)])],
 'delete':[('l',[(5,6),(19,6)]),('l',[(8,6),(8,3),(16,3),(16,6)]),('l',[(7,6),(8,21),(16,21),(17,6)]),('l',[(10,10),(10,17)]),('l',[(14,10),(14,17)])],
 'fit':[('l',[(3,9),(3,3),(9,3)]),('l',[(15,3),(21,3),(21,9)]),('l',[(21,15),(21,21),(15,21)]),('l',[(9,21),(3,21),(3,15)])],
 'zoom_in':[('e',(3,3,16,16)),('l',[(15,15),(22,22)]),('l',[(6,10),(13,10)]),('l',[(10,6),(10,13)])],
 'zoom_out':[('e',(3,3,16,16)),('l',[(15,15),(22,22)]),('l',[(6,10),(13,10)])],
 'path':[('l',[(3,19),(9,19),(9,6),(21,6)]),('e',(1,17,5,21)),('e',(19,4,23,8))],
 'gather':[('l',[(3,4),(12,12),(21,12)]),('l',[(3,20),(12,12)]),('e',(10,10,14,14))],
 'sun':[('e',(7,7,17,17)),('l',[(12,1),(12,4)]),('l',[(12,20),(12,23)]),('l',[(1,12),(4,12)]),('l',[(20,12),(23,12)]),('l',[(3,3),(5,5)]),('l',[(19,19),(21,21)])],
 'chart':[('l',[(3,3),(3,21),(22,21)]),('l',[(6,17),(10,10),(14,14),(20,5)])],
 'data':[('e',(3,3,21,9)),('l',[(3,6),(3,18),(7,21),(17,21),(21,18),(21,6)]),('l',[(3,12),(7,15),(17,15),(21,12)])],
 'run':[('p',[(7,3),(21,12),(7,21)])],
 'export':[('l',[(4,13),(4,21),(20,21),(20,13)]),('l',[(12,16),(12,2)]),('l',[(7,7),(12,2),(17,7)])],
 'eye':[('l',[(2,12),(7,6),(17,6),(22,12),(17,18),(7,18),(2,12)]),('e',(9,9,15,15))],
 'move':[('l',[(12,2),(12,22)]),('l',[(2,12),(22,12)]),('l',[(8,6),(12,2),(16,6)]),('l',[(8,18),(12,22),(16,18)]),('l',[(6,8),(2,12),(6,16)]),('l',[(18,8),(22,12),(18,16)])],
}

def plain(text):
    return re.sub(r'\s+',' ',''.join(c for c in str(text) if unicodedata.category(c) not in ('So','Mn') and c not in '\ufe0f')).strip()

def icon_key(label):
    low=plain(label).lower()
    if low=='+':return 'zoom_in'
    if low=='-':return 'zoom_out'
    if not low:return 'fit'
    for words,key in [(['pdf','report'],'pdf'),(['electrical values'],'eye'),(['reflow','arrange'],'diagram'),(['delete','clear'],'delete'),(['auto generate'],'diagram'),(['calculate','simulate','run'],'run'),(['project','open'],'folder'),(['display','settings','configuration'],'settings'),(['scale','measure'],'ruler'),(['routing area','polygon'],'polygon'),(['zone'],'zones'),(['panel'],'panel'),(['layout','spreadsheet'],'grid'),(['string'],'string'),(['mppt','inverter'],'inverter'),(['links'],'link'),(['custom element','new'],'plus'),(['gather'],'gather'),(['cable path'],'path'),(['routes'],'path'),(['shadow','solar'],'sun'),(['results','chart','economics'],'chart'),(['data','import'],'data'),(['export'],'export'),(['zoom in'],'zoom_in'),(['zoom out'],'zoom_out'),(['fit','reset'],'fit'),(['block'],'zones')]:
        if any(w in low for w in words):return key
    return 'settings'

def raster(key,size=12,color='#344653'):
    image=Image.new('RGBA',(size*3,size*3));d=ImageDraw.Draw(image);scale=size*3/24
    for kind,coords in ICONS[key]:
        if kind in ('l','p'):
            pts=[(round(x*scale),round(y*scale)) for x,y in coords]
            d.line(pts+([pts[0]] if kind=='p' else []),fill=color,width=max(1,round(1.65*scale)),joint='curve')
        else:
            box=tuple(round(v*scale) for v in coords)
            (d.rectangle if kind=='r' else d.ellipse)(box,outline=color,width=max(1,round(1.65*scale)))
    return image.resize((size,size),Image.Resampling.LANCZOS)

DESCRIPTIONS={
 'folder':'Open or save the project and manage the roof image.',
 'settings':'Configure the parameters of this tab. Review values before calculating.',
 'pdf':'Export the engineering report, vector plan sheets and editable LaTeX source.',
 'ruler':'Calibrate scale or add a black double-arrow dimension; choose aligned, horizontal or vertical.',
 'polygon':'Draw a routing area or transform its selected vertices. Enter its installation elevation.',
 'zones':'Create and manage installation zones or inverter blocks, as named below.',
 'panel':'Set module dimensions, tilt and azimuth.',
 'grid':'Generate the panel layout or manage spreadsheet cells, as named below.',
 'string':'Create or edit the electrical order of modules in a string.',
 'inverter':'Place equipment or assign strings to MPPT inputs.',
 'diagram':'Rebuild or reflow the diagram using the actual block sizes and connection lanes.',
 'link':'Choose a link style, then left-click its two endpoints.',
 'plus':'Add the element named below.',
 'delete':'Delete the selected element or clear the named data.',
 'fit':'Restore the reference zoom or fit the plan.',
 'zoom_in':'Enlarge the current drawing or spreadsheet.',
 'zoom_out':'Reduce the current drawing or spreadsheet.',
 'path':'Draw cable trays, calculate conductor routes or export their inventory.',
 'gather':'Set the shared cable exit point for an installation zone.',
 'sun':'Configure the solar or shadow study.',
 'chart':'Open results. Day and month charts separate load supply, PV use and battery state.',
 'data':'Import the consumption or weather inputs used for calculations.',
 'run':'Run the named calculation with the current inputs.',
 'export':'Export the named result.',
 'eye':'Show or hide electrical values; block spacing is recalculated automatically.',
 'move':'Move the selected elements.',
}

# Each distinct tool has a semantic silhouette. Repeated actions (Undo, Redo,
# Save) deliberately keep the same symbol wherever they appear.
ICONS.update({
 'battery':[('r',(3,6,20,18)),('r',(20,10,23,14)),('l',[(6,12),(12,12)]),('l',[(9,9),(9,15)]),('l',[(15,12),(18,12)])],
 'undo':[('l',[(8,5),(3,10),(8,15)]),('l',[(3,10),(14,10),(19,13),(19,19)])],
 'redo':[('l',[(16,5),(21,10),(16,15)]),('l',[(21,10),(10,10),(5,13),(5,19)])],
 'save':[('r',(3,3,21,21)),('r',(7,3,16,9)),('r',(7,14,17,21))],
 'book':[('l',[(12,5),(7,3),(2,3),(2,20),(7,20),(12,22),(17,20),(22,20),(22,3),(17,3),(12,5),(12,22)])],
 'calculator':[('r',(5,2,19,22)),('r',(8,5,16,9)),('r',(8,12,10,14)),('r',(14,12,16,14)),('r',(8,17,10,19)),('r',(14,17,16,19))],
 'formula':[('l',[(17,3),(13,3),(10,21),(6,21)]),('l',[(6,10),(17,10)]),('l',[(16,16),(22,22)]),('l',[(22,16),(16,22)])],
 'stop':[('r',(5,5,19,19))],
 'close':[('l',[(5,5),(19,19)]),('l',[(19,5),(5,19)])],
 'coin':[('e',(3,3,21,21)),('l',[(16,7),(8,7),(8,12),(16,12),(16,17),(8,17)]),('l',[(12,4),(12,20)])],
 'weight':[('e',(9,2,15,8)),('l',[(6,8),(18,8),(22,22),(2,22),(6,8)])],
 'obstacle':[('l',[(6,21),(6,6),(17,2),(17,17),(6,21)]),('l',[(17,17),(22,21),(6,21)]),('l',[(6,6),(11,10),(22,6)])],
 'target':[('e',(2,2,22,22)),('e',(7,7,17,17)),('l',[(12,0),(12,7)]),('l',[(12,17),(12,24)]),('l',[(0,12),(7,12)]),('l',[(17,12),(24,12)])],
 'row':[('r',(3,3,21,21)),('l',[(3,9),(21,9)]),('l',[(3,15),(21,15)]),('l',[(6,12),(18,12)])],
 'renumber':[('l',[(3,4),(7,2),(7,10)]),('l',[(3,14),(8,14),(8,17),(3,22),(8,22)]),('l',[(12,6),(22,6)]),('l',[(12,18),(22,18)])],
 'check':[('l',[(3,12),(9,19),(21,4)])],
 'refresh':[('l',[(20,9),(17,4),(8,4),(3,10),(4,18),(10,21),(18,18)]),('l',[(15,9),(21,9),(21,3)])],
 'photo':[('r',(2,4,22,21)),('e',(5,7,9,11)),('l',[(3,19),(10,13),(14,16),(18,10),(22,15)])],
 'clock':[('e',(3,3,21,21)),('l',[(12,6),(12,12),(17,15)])],
 'calendar':[('r',(3,5,21,22)),('l',[(3,10),(21,10)]),('l',[(7,2),(7,8)]),('l',[(17,2),(17,8)]),('l',[(7,14),(10,14)]),('l',[(14,18),(17,18)])],
 'previous':[('l',[(16,4),(6,12),(16,20)])],
 'next':[('l',[(8,4),(18,12),(8,20)])],
 'wrench':[('l',[(13,2),(13,7),(17,11),(22,11),(20,15),(15,15),(6,23),(1,18),(10,10),(9,5),(13,2)])],
 'bars':[('l',[(3,2),(3,22),(23,22)]),('r',(6,13,9,20)),('r',(12,7,15,20)),('r',(18,3,21,20))],
 'diameter':[('e',(3,3,21,21)),('l',[(2,22),(22,2)]),('l',[(2,17),(2,22),(7,22)]),('l',[(17,2),(22,2),(22,7)])],
})

def _composite(base,badge):
    result=[]
    for key,scale,ox,oy in ((base,.72,0,0),(badge,.43,13.5,13.5)):
        for kind,points in ICONS[key]:
            if kind in ('l','p'):coords=[(x*scale+ox,y*scale+oy) for x,y in points]
            else:coords=(points[0]*scale+ox,points[1]*scale+oy,points[2]*scale+ox,points[3]*scale+oy)
            result.append((kind,coords))
    return result

COMPOSITES={
 'file_menu':('folder','pdf'),'bess_calculate':('battery','calculator'),
 'save_as':('save','plus'),'open_project':('folder','next'),'display':('eye','settings'),
 'questionnaire':('row','check'),'model':('calculator','settings'),'generate':('grid','run'),
 'generate_strings':('string','run'),'block_actions':('zones','inverter'),'mppt_actions':('inverter','link'),
 'string_actions':('string','settings'),'string_routes':('string','path'),'string_size':('string','diameter'),
 'route_calculate':('path','run'),'section_calculate':('diameter','calculator'),'all_strings':('string','calculator'),
 'cable_areas':('polygon','path'),'cable_paths':('path','panel'),'routing_export':('path','export'),
 'economics_export':('coin','export'),'csv_export':('row','export'),'image_export':('photo','export'),
 'diagram_fit':('diagram','fit'),'diagram_reflow':('diagram','move'),'diagram_generate':('diagram','run'),
 'diagram_values':('diagram','eye'),'shadow_settings':('sun','settings'),'shadow_run':('sun','run'),
 'shadow_chart':('sun','chart'),'simulation':('sun','calendar'),'drawing_export':('polygon','export'),
 'copy_module':('panel','next'),'inverter_place':('inverter','target'),'panel_add':('panel','plus'),
 'panel_settings':('panel','settings'),'string_edit':('string','wrench'),'row_delete':('row','delete'),
 'node_delete':('diagram','delete'),'refresh_checks':('check','refresh'),'economic_update':('coin','refresh'),
 'longest_route':('path','ruler'),'input_save':('save','check'),'settings_save':('save','settings'),
 'layout':('grid','panel'),'data_files':('data','folder'),'insert':('row','plus'),
 'move_up':('move','previous'),'move_down':('move','next'),'results':('bars','check'),
}
for key,pair in COMPOSITES.items():ICONS[key]=_composite(*pair)
ACTION_ICONS={
 'renumber panels':'renumber','project':'folder','file':'file_menu','open another project…':'open_project','open selected':'open_project',
 'save as…':'save_as','undo':'undo','redo':'redo','configuration':'questionnaire','model settings':'model',
 'engineering report pdf':'pdf','export screenshot':'image_export','quick start':'book',
 'ƒx formula guide':'formula','formula guide':'formula','∑ engineering calculations':'calculator',
 'engineering calculations':'calculator','display settings':'display','scale and measurements':'ruler',
 'zones':'zones','cable routing area':'cable_areas','panel…':'panel_settings','layout':'layout',
 'block actions':'block_actions','string actions':'string_actions','generate strings':'generate_strings',
 'mppt actions':'mppt_actions','active block inverter':'inverter_place','cable paths':'cable_paths',
 'gathering points':'gather','string routes':'string_routes','calculate / refresh routes':'route_calculate',
 'export route inventory csv':'routing_export','calculate cross-section':'section_calculate',
 'calculate all strings':'all_strings','edit selected string…':'string_edit','cable mass by section…':'weight',
 'auto generate (strings → mppt → inverters)':'diagram_generate','reflow diagram':'diagram_reflow',
 'fit diagram':'diagram_fit','show electrical values':'diagram_values','custom element':'plus',
 'custom links':'link','delete selected element':'node_delete','delete selected row':'row_delete',
 'shadow settings':'shadow_settings','obstacle':'obstacle','multi-day simulation':'simulation',
 'drawing / exports':'drawing_export','data':'data_files','calculate 3 options':'bess_calculate',
 'charts':'bars','results':'results','chart for this simulation':'shadow_chart','run simulation':'shadow_run',
 'cancel calculation':'stop','cancel':'close','close':'close','tools':'wrench','settings':'settings',
 'row':'row','insert':'insert','move up':'move_up','move down':'move_down','next day':'next',
 'previous day':'previous','copy pv module from equipment sheet':'copy_module','add panel':'panel_add',
 'place on image':'target','update economics':'economic_update','refresh':'refresh',
 'refresh checks':'refresh_checks','export economics csv':'economics_export','export csv':'csv_export',
 'save csv…':'save','save inputs and check':'input_save','save settings and project':'settings_save',
 'use longest calculated route':'longest_route','zoom':'zoom_in',
}
_category_icon_key=icon_key

def icon_key(label):
    clean=plain(label).lower()
    return ACTION_ICONS.get(clean,_category_icon_key(label))

for key in ICONS:DESCRIPTIONS.setdefault(key,'Use '+key.replace('_',' ')+' for the action named beside the icon.')
