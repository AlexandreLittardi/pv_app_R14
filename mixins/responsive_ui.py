"""Wrapping native icon toolbars, without overflow menus or duplicated fields."""
import tkinter as tk
from tkinter import ttk
from toolbar_icons import icon_key, raster, plain
from PIL import ImageTk

class ResponsiveUIMixin:
    def _on_ribbon_tab_changed(self,event):
        if hasattr(self,'canvas_frame') and not self.canvas_frame.winfo_manager():
            self.canvas_frame.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        return super()._on_ribbon_tab_changed(event)

    def _build_root_scroller(self):
        # Keep the historical method name for callers, remove the scrolling shell.
        self.ui_content=ttk.Frame(self.root)
        self.ui_content.pack(fill=tk.BOTH,expand=True)

    def _install_responsive_ui(self):
        # Navigation uses the notebook tabs alone; compact tab titles on small screens.
        self._full_tab_titles=('Home','Installation area','Layout and blocks','Stringing',
                               'MPPT assignment','Shadow','Spreadsheet',
                               'Electrical single-line diagram','Cabling','Energy / BESS')
        self._auto_fit=True
        self._install_compact_zoom()
        self._toolbars={};self._resize_job=None
        for ident in self.ribbon_notebook.tabs():
            tab=self.root.nametowidget(ident)
            items=[]
            for w in tab.winfo_children():
                if w.winfo_manager()=='pack':items.append((w,dict(w.pack_info())))
            self._toolbars[str(tab)]=(tab,items,None,None)
            self._iconize_toolbar(tab)
            tab.bind('<Configure>',self._schedule_responsive,add='+')
        self.ribbon_notebook.bind('<<NotebookTabChanged>>',self._responsive_tab_changed,add='+')
        self.root.bind('<Configure>',self._schedule_responsive,add='+')
        self.root.bind_all('<Map>',self._cap_mapped_dialog,add='+')
        self.root.after_idle(self._layout_responsive)

    def _paginate_shadow_panel(self):
        pass  # Shadow parameters remain in one scrollable left sidebar.

    def _install_compact_zoom(self):
        for ident in self.ribbon_notebook.tabs():
            tab=self.root.nametowidget(ident)
            zoom=next((w for w in tab.winfo_children() if isinstance(w,ttk.Menubutton)
                       and 'Zoom' in str(w.cget('text'))),None)
            if zoom is None:continue
            zoom.pack_forget();zoom.destroy()
            group=ttk.Frame(tab)
            spreadsheet=tab is self.tab_material
            commands=((lambda:self._zoom_spreadsheet(1/1.2),self._reset_spreadsheet_zoom,
                       lambda:self._zoom_spreadsheet(1.2)) if spreadsheet else
                      (lambda:self._zoom_button_change(1/1.2),self._reset_zoom,
                       lambda:self._zoom_button_change(1.2)))
            for label,command in zip(('-', '⤾', '+'),commands):
                ttk.Button(group,text=label,width=2,command=command).pack(side=tk.LEFT)
            group.pack(side=tk.RIGHT,padx=2)

    def _responsive_tab_changed(self,event=None):
        self._schedule_responsive()

    def _fit_tab_labels(self):
        width=self.ribbon_frame.winfo_width()
        if width<560:
            titles=('Home','Area','PV','Str','MPPT','Shade','Sheet','SLD','Wire','BESS')
        elif width<740:
            titles=('Home','Area','PV','Strings','MPPT','Shade','Sheet','Diagram','Cables','BESS')
        elif width<1250:
            titles=('Home','Installation','Layout','Stringing','MPPT','Shadow',
                    'Spreadsheet','Single-line','Cabling','Energy / BESS')
        else:
            titles=self._full_tab_titles
        for ident,title in zip(self.ribbon_notebook.tabs(),titles):
            if self.ribbon_notebook.tab(ident,'text')!=title:
                self.ribbon_notebook.tab(ident,text=title)

    def _schedule_responsive(self,event=None):
        if not hasattr(self,'_toolbars'):return
        if self._resize_job is not None:self.root.after_cancel(self._resize_job)
        self._resize_job=self.root.after(70,self._layout_responsive)

    def _layout_responsive(self):
        self._resize_job=None
        self._fit_tab_labels()
        for tab,items,_,_ in self._toolbars.values():
            if not tab.winfo_ismapped():continue
            width=max(180,tab.winfo_width()-12);x=4;y=4;row_height=34
            for widget,info in items:
                widget.pack_forget()
                if isinstance(widget,ttk.Label) and len(str(widget.cget('text')))>45:
                    widget.configure(wraplength=max(160,width-16))
                cost=min(width,widget.winfo_reqwidth()+8)
                if x+cost>width and x>4:x=4;y+=row_height+4;row_height=34
                height=max(30,widget.winfo_reqheight())
                widget.place(x=x,y=y,width=max(8,cost-6),height=height)
                row_height=max(row_height,height);x+=cost
            self.ribbon_notebook.configure(height=y+row_height+8)
        width=self.main_container.winfo_width()
        active=[]
        for name in ('stringing','equipment','shadow','material','diagram','notes'):
            panel=getattr(self,'side_panel_'+name,None)
            if panel is None:continue
            panel.pack_propagate(False)
            panel.configure(width=max(180,min(430 if name=='material' else 360,int(width*.30))))
            if panel.winfo_manager()=='pack':
                active.append(panel)
                panel.pack_configure(fill=tk.Y,expand=False)
                for child in panel.winfo_children():
                    if isinstance(child,ttk.Label) and child.cget('wraplength'):
                        child.configure(wraplength=max(200,panel.winfo_width()-20))
        if self._get_active_tab_index() not in (0,9) and not self.canvas_frame.winfo_manager():
            options={'side':tk.LEFT,'fill':tk.BOTH,'expand':True}
            if active:options['before']=active[0]
            self.canvas_frame.pack(**options)
        if hasattr(self,'stats_frame'):
            if width<900:self.stats_frame.place_forget()
            elif self._get_active_tab_index()!=6:self.stats_frame.place(relx=1.,rely=1.,anchor='se',x=-15,y=-15)
        if self._auto_fit and self.canvas_frame.winfo_manager() and self._get_active_tab_index()!=7:
            self.root.after_idle(self._apply_roof_fit)

    def _fit_roof_to_window(self):
        self._auto_fit=True
        self._apply_roof_fit()

    def _apply_roof_fit(self):
        if not self.roof_pil_img or self.canvas.winfo_width()<50:return
        zoom=min((self.canvas.winfo_width()-10)/self.roof_pil_img.width,
                 (self.canvas.winfo_height()-10)/self.roof_pil_img.height)
        zoom=max(.03,min(3.,zoom))
        if abs(zoom-self.zoom_level)>.002:
            self.zoom_level=zoom;self.cell_size_px=max(1,int(40*zoom));self.draw_grid()
            self.canvas.xview_moveto(0);self.canvas.yview_moveto(0)

    def _zoom_button_change(self,factor):
        self._auto_fit=False
        return super()._zoom_button_change(factor)

    def _zoom_at_pointer(self,event,delta):
        self._auto_fit=False
        return super()._zoom_at_pointer(event,delta)

    def _iconize_toolbar(self,tab):
        self._toolbar_icon_images=getattr(self,'_toolbar_icon_images',{})
        self._toolbar_icon_catalog=getattr(self,'_toolbar_icon_catalog',{})
        catalog=[]
        def visit(parent):
            for widget in parent.winfo_children():
                if isinstance(widget,(ttk.Button,ttk.Menubutton)):
                    label=plain(widget.cget('text'));key=icon_key(label)
                    if not label:label='Reset zoom (100%)'
                    if label in ('+','-'):label='Zoom in' if label=='+' else 'Zoom out'
                    if key not in self._toolbar_icon_images:self._toolbar_icon_images[key]=ImageTk.PhotoImage(raster(key),master=self.root)
                    widget.configure(image=self._toolbar_icon_images[key],text=label,compound='left',width=0)
                    commands=[]
                    if isinstance(widget,ttk.Menubutton) and str(widget.cget('menu')):
                        menu=self.root.nametowidget(widget.cget('menu'))
                        def clean(m):
                            end=m.index('end')
                            if end is None:return
                            for i in range(end+1):
                                if m.type(i) in ('separator','tearoff'):continue
                                caption=plain(m.entrycget(i,'label'));m.entryconfigure(i,label=caption);commands.append(caption)
                                if m.type(i)=='cascade':clean(self.root.nametowidget(m.entrycget(i,'menu')))
                        clean(menu)
                    catalog.append((key,label,commands))
                elif isinstance(widget,(ttk.Frame,ttk.LabelFrame)):visit(widget)
        visit(tab);self._toolbar_icon_catalog[str(tab)]=catalog

    def _fit_dialog(self,window,width,height):
        sw=self.root.winfo_screenwidth();sh=self.root.winfo_screenheight()
        width=min(width,max(300,sw-40));height=min(height,max(250,sh-80))
        window.geometry(f'{width}x{height}+{max(0,(sw-width)//2)}+{max(0,(sh-height)//2)}')
        window.minsize(min(420,width),min(280,height))

    def _cap_mapped_dialog(self,event):
        w=event.widget
        if not isinstance(w,tk.Toplevel) or w.overrideredirect() or getattr(w,'_initial_fit_done',False):return
        w._initial_fit_done=True
        self.root.after_idle(lambda:self._fit_dialog(w,w.winfo_width(),w.winfo_height()) if w.winfo_exists() else None)
