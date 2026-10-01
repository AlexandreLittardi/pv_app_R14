"""Desktop integration smoke test; requires a real Tk display (e.g. Windows)."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import messagebox
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import PVLayoutRibbonApp
from PIL import Image

with tempfile.TemporaryDirectory() as tmp:
    root=tk.Tk();errors=[]
    root.report_callback_exception=lambda *args:errors.append(args)
    app=PVLayoutRibbonApp(root);root.update()
    assert 'R14' in root.title()
    app.roof_pil_img=Image.new('RGB',(900,700),'white')
    app.roof_image_path=None;app.px_per_mm=.1
    app.roof_zones=[{'id':1,'x1':30,'y1':30,'x2':700,'y2':650,'angle_deg':30,'installation_height_m':8,'z_mm':11000}]
    app.roof_polygons=[{'id':1,'points':[(0,0),(850,0),(850,680),(0,680)],'installation_height_m':8}]
    app.generate_panels_from_zones();assert app.panels and not app._layout_issues()
    for i in range(10):
        app.ribbon_notebook.select(i);root.update();app.draw_grid();root.update()
    app.ribbon_notebook.select(7);root.update()
    app.diagram_nodes={'custom::1':{'x':150,'y':150,'label':'Test A','type':'custom'},'custom::2':{'x':500,'y':150,'label':'Test B','type':'custom'}}
    app.diagram_links=[];app.diagram_selected_nodes=set(app.diagram_nodes);app.diagram_selected_node='custom::1'
    app.zoom_level=1;app._reflow_diagram();root.update()
    original={k:(v['x'],v['y']) for k,v in app.diagram_nodes.items()}
    event=lambda x,y:SimpleNamespace(x=int(x),y=int(y),state=0)
    app.on_left_press(event(100,100));app.on_left_drag(event(125,130));app.on_left_release(event(125,130))
    assert original=={k:(v['x'],v['y']) for k,v in app.diagram_nodes.items()}
    node=app.diagram_nodes['custom::1']
    sx=node['x']-app.canvas.canvasx(0);sy=node['y']-app.canvas.canvasy(0)
    app.on_right_press(event(sx,sy));app.on_right_drag(event(sx+25,sy+30));app.on_right_release(event(sx+25,sy+30))
    for k,n in app.diagram_nodes.items():
        assert abs(n['x']-original[k][0]-25)<1
        assert abs(n['y']-original[k][1]-30)<1
    from tkinter import ttk
    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)
    for width in (640,1100):
        root.geometry(f'{width}x750');root.update();app._layout_responsive();root.update()
        assert app.canvas_frame.winfo_manager()
        for tab,items,_,_ in app._toolbars.values():
            for w in descendants(tab):
                if isinstance(w,(ttk.Button,ttk.Menubutton)):
                    assert w.cget('image'),str(w)
                    assert w.cget('text') and w.cget('compound')=='left'
    assert 'Toolbar icon guide' not in [app.home_guide_notebook.tab(t,'text') for t in app.home_guide_notebook.tabs()]
    for ident in app.ribbon_notebook.tabs():
        for widget in descendants(root.nametowidget(ident)):
            if isinstance(widget,(ttk.Button,ttk.Menubutton)):
                assert not hasattr(widget,'_icon_tooltip')
                assert 'Zone rotation' not in str(widget.cget('text'))
    assert not hasattr(app,'_show_zone_rotation')
    app.cable_string_params={'String 1':{'current_a':12.,'voltage_v':640.}}
    app.cable_mass_by_section={'4':.05,'6':.08}
    app.measures=[{'p1':(0,0),'p2':(100,200),'label':(50,-20),'axis':'horizontal'}]
    app.current_project_filepath=str(Path(tmp)/'fixture.json');app.project_name='GUI smoke fixture'
    app.bess_entries['discharge_kw'].delete(0,'end');app.bess_entries['discharge_kw'].insert(0,'200')
    with patch.object(messagebox,'showinfo'),patch.object(messagebox,'showerror') as err:
        app.save_project()
        app._load_project_file(app.current_project_filepath)
        assert not err.called,err.call_args
    assert app.cable_string_params=={'String 1':{'current_a':12.,'voltage_v':640.}}
    assert app.cable_mass_by_section=={'4':.05,'6':.08}
    import json
    saved=json.loads(Path(app.current_project_filepath).read_text())
    assert saved['schema_version']==2
    assert saved['project_uid']
    assert callable(app.undo_project) and callable(app.redo_project)
    for tab in range(10):
        app.ribbon_notebook.select(tab);root.update()
        app._record_history();original=app.project_notes
        app.project_notes='Undo fixture '+str(tab)
        app.txt_notes.delete('1.0','end');app.txt_notes.insert('1.0',app.project_notes)
        app.undo_project();root.update();assert app.project_notes==original
        app.redo_project();root.update();assert app.project_notes=='Undo fixture '+str(tab)
    assert len(app._history_buttons)==20
    app._show_model_settings();root.update()
    assert app._configuration_questionnaire.winfo_viewable()
    app._configuration_questionnaire.destroy()
    assert app.roof_polygons[0]['installation_height_m']==8
    assert app.roof_zones[0]['z_mm']==11000
    assert app.measures[0]['axis']=='horizontal'
    assert float(app.bess_entries['discharge_kw'].get())==200
    app._open_equipment_configuration();root.update()
    assert app._equipment_window.winfo_viewable()
    assert app.material_notebook.master==app._equipment_window
    assert not errors,errors
    root.destroy()
print('R14 desktop integration passed')
