"""Cell-range selection, fill handle, formula references and clipboard actions."""
import re
import tkinter as tk
from mixins.spreadsheet_tools import cell_id, col_index, col_letter


_REFERENCE = re.compile(r'(?<![A-Za-z_0-9])([A-Za-z]+)([1-9][0-9]*)(?![A-Za-z_0-9])')

def shift_formula(formula, dr, dc):
    """Shift relative references when a formula is dragged to another cell."""
    if not isinstance(formula,str) or not formula.startswith('='):return formula
    def moved(match):
        col=max(0,col_index(match.group(1))+dc)
        row=max(1,int(match.group(2))+dr)
        return f'{col_letter(col)}{row}'
    return _REFERENCE.sub(moved,formula)


class SpreadsheetInteractionsMixin:
    def _rebuild_spreadsheet_grid(self):
        self.spreadsheet_fill_handle=None
        self.spreadsheet_range_anchor=None
        self.spreadsheet_range_end=None
        self._spreadsheet_fill_outline=None
        return super()._rebuild_spreadsheet_grid()

    def _init_spreadsheet_state(self):
        super()._init_spreadsheet_state()
        self.spreadsheet_range_anchor=None
        self.spreadsheet_range_end=None
        self.spreadsheet_fill_handle=None
        self.spreadsheet_drag_mode=None

    def _build_material_spreadsheet_area(self):
        super()._build_material_spreadsheet_area()
        grid=self.spreadsheet_data_canvas
        grid.bind('<B1-Motion>',self._spreadsheet_cell_drag)
        grid.bind('<ButtonRelease-1>',self._spreadsheet_cell_release)
        grid.bind('<Control-c>',self._spreadsheet_copy)
        grid.bind('<Control-v>',self._spreadsheet_paste)

    def _spreadsheet_rect_coords(self,first,last):
        r0,r1=sorted((first[0],last[0]))
        c0,c1=sorted((first[1],last[1]))
        return (self._spreadsheet_col_x(c0),self._spreadsheet_row_y(r0),
                self._spreadsheet_col_x(c1)+self._spreadsheet_col_w(c1),
                self._spreadsheet_row_y(r1)+self._spreadsheet_row_h(r1))

    def _draw_spreadsheet_selection(self):
        super()._draw_spreadsheet_selection()
        grid=self.spreadsheet_data_canvas
        if self.spreadsheet_selected is None:return
        anchor=self.spreadsheet_range_anchor or self.spreadsheet_selected
        end=self.spreadsheet_range_end or self.spreadsheet_selected
        x0,y0,x1,y1=self._spreadsheet_rect_coords(anchor,end)
        if self.spreadsheet_selection_rect is not None:
            grid.coords(self.spreadsheet_selection_rect,x0,y0,x1,y1)
            grid.tag_raise(self.spreadsheet_selection_rect)
        if self.spreadsheet_fill_handle is None:
            self.spreadsheet_fill_handle=grid.create_rectangle(0,0,0,0,fill='#1565C0',outline='white')
        grid.coords(self.spreadsheet_fill_handle,x1-5,y1-5,x1+3,y1+3)
        grid.tag_raise(self.spreadsheet_fill_handle)

    def _insert_clicked_cell_reference(self,cell):
        entry=self.spreadsheet_edit_entry if self.spreadsheet_editing_cell is not None else self.spreadsheet_formula_entry
        if entry is None or not entry.get().strip().startswith('='):return False
        # Keep editing the source cell. Its FocusOut handler is not invoked.
        pos=entry.index(tk.INSERT)
        entry.insert(pos,cell_id(*cell))
        entry.icursor(pos+len(cell_id(*cell)))
        entry.focus_set()
        return True

    def _on_spreadsheet_cell_click(self,event):
        cell=self._spreadsheet_cell_at_event(event)
        if cell is None:return
        if self.spreadsheet_editing_cell is not None and self.spreadsheet_editing_cell!=cell:
            if self._insert_clicked_cell_reference(cell):return 'break'
        if (self.spreadsheet_formula_entry.focus_get()==self.spreadsheet_formula_entry and
            self._insert_clicked_cell_reference(cell)):
            return 'break'
        grid=self.spreadsheet_data_canvas
        if self.spreadsheet_selected is not None and self.spreadsheet_fill_handle is not None:
            x0,y0,x1,y1=grid.coords(self.spreadsheet_fill_handle)
            x,y=grid.canvasx(event.x),grid.canvasy(event.y)
            if x0-3<=x<=x1+3 and y0-3<=y<=y1+3:
                self.spreadsheet_drag_mode='fill'
                return 'break'
        if event.state & 0x0001 and self.spreadsheet_selected is not None:
            self.spreadsheet_range_anchor=self.spreadsheet_range_anchor or self.spreadsheet_selected
            self.spreadsheet_range_end=cell
            self.spreadsheet_drag_mode='select'
            self._draw_spreadsheet_selection()
            return 'break'
        self.spreadsheet_range_anchor=cell
        self.spreadsheet_range_end=cell
        self.spreadsheet_drag_mode='select'
        return super()._on_spreadsheet_cell_click(event)

    def _spreadsheet_cell_drag(self,event):
        if self.spreadsheet_drag_mode is None:return
        cell=self._spreadsheet_cell_at_event(event)
        if cell is None:return
        if self.spreadsheet_drag_mode=='select':
            self.spreadsheet_range_end=cell
            self._draw_spreadsheet_selection()
        elif self.spreadsheet_drag_mode=='fill':
            self._spreadsheet_fill_target=cell
            x0,y0,x1,y1=self._spreadsheet_rect_coords(self.spreadsheet_range_anchor or self.spreadsheet_selected,cell)
            grid=self.spreadsheet_data_canvas
            if not getattr(self,'_spreadsheet_fill_outline',None):
                self._spreadsheet_fill_outline=grid.create_rectangle(x0,y0,x1,y1,outline='#1976D2',dash=(4,2),width=2)
            else:grid.coords(self._spreadsheet_fill_outline,x0,y0,x1,y1)

    def _spreadsheet_cell_release(self,event):
        if self.spreadsheet_drag_mode=='fill' and getattr(self,'_spreadsheet_fill_target',None) is not None:
            self._spreadsheet_fill_to(self._spreadsheet_fill_target)
        self.spreadsheet_drag_mode=None
        self._spreadsheet_fill_target=None
        if getattr(self,'_spreadsheet_fill_outline',None):
            self.spreadsheet_data_canvas.delete(self._spreadsheet_fill_outline)
            self._spreadsheet_fill_outline=None

    def _spreadsheet_fill_to(self,target):
        if self.spreadsheet_selected is None:return
        anchor=self.spreadsheet_range_anchor or self.spreadsheet_selected
        end=self.spreadsheet_range_end or anchor
        r0,r1=sorted((anchor[0],end[0]))
        c0,c1=sorted((anchor[1],end[1]))
        rt,ct=target
        rows=self.material_spreadsheet['rows'];cols=self.material_spreadsheet['cols']
        cells=self.material_spreadsheet['cells']
        source={(r,c):cells.get(cell_id(r,c),'') for r in range(r0,r1+1) for c in range(c0,c1+1)}
        vertical=r0!=r1 and c0==c1
        horizontal=c0!=c1 and r0==r1
        def numeric_pair(first,second):
            try:return float(first),float(second)
            except (ValueError,TypeError):return None
        for r in range(max(0,min(r0,rt)),min(rows,max(r1,rt)+1)):
            for c in range(max(0,min(c0,ct)),min(cols,max(c1,ct)+1)):
                if r0<=r<=r1 and c0<=c<=c1:continue
                sr=r0+(r-r0)%(r1-r0+1)
                sc=c0+(c-c0)%(c1-c0+1)
                raw=source[(sr,sc)]
                if vertical:
                    pair=numeric_pair(source[(r0,c0)],source[(r0+1,c0)])
                    if pair and r>r1:raw=str(pair[0]+(pair[1]-pair[0])*(r-r0))
                elif horizontal:
                    pair=numeric_pair(source[(r0,c0)],source[(r0,c0+1)])
                    if pair and c>c1:raw=str(pair[0]+(pair[1]-pair[0])*(c-c0))
                raw=shift_formula(raw,r-sr,c-sc)
                address=cell_id(r,c)
                if raw=='':cells.pop(address,None)
                else:cells[address]=raw
        self.spreadsheet_range_end=target
        self._refresh_spreadsheet()
        self._draw_spreadsheet_selection()

    def _spreadsheet_copy(self,event=None):
        if self.spreadsheet_selected is None:return 'break'
        a=self.spreadsheet_range_anchor or self.spreadsheet_selected
        b=self.spreadsheet_range_end or a
        r0,r1=sorted((a[0],b[0]));c0,c1=sorted((a[1],b[1]))
        cells=self.material_spreadsheet['cells']
        value='\n'.join('\t'.join(str(cells.get(cell_id(r,c),'')) for c in range(c0,c1+1)) for r in range(r0,r1+1))
        self.root.clipboard_clear();self.root.clipboard_append(value)
        return 'break'

    def _spreadsheet_paste(self,event=None):
        if self.spreadsheet_selected is None:return 'break'
        try:text=self.root.clipboard_get()
        except tk.TclError:return 'break'
        r0,c0=self.spreadsheet_selected
        cells=self.material_spreadsheet['cells']
        for dr,line in enumerate(text.splitlines()):
            for dc,value in enumerate(line.split('\t')):
                r,c=r0+dr,c0+dc
                if r>=self.material_spreadsheet['rows'] or c>=self.material_spreadsheet['cols']:continue
                address=cell_id(r,c)
                if value:cells[address]=value
                else:cells.pop(address,None)
        self._refresh_spreadsheet();self._draw_spreadsheet_selection()
        return 'break'
