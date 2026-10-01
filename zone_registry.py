"""Persistent zone coordinate ranges; migrate only when a range must grow."""
import uuid

def allocate_ranges(zones,specs,remap=None):
    # Preserve the legacy row_base on first load. Capacity is persistent thereafter.
    cursor=max((int(z.get('row_base',i*100))+max(int(z.get('row_capacity',100)),int(z.get('rows',0))) for i,z in enumerate(zones)),default=0)
    for i,(z,(rows,cols,ox,oy)) in enumerate(zip(zones,specs)):
        z.setdefault('uid',uuid.uuid4().hex)
        base=int(z.get('row_base',i*100));cap=int(z.get('row_capacity',100))
        occupied=[(int(other.get('row_base',j*100)),int(other.get('row_base',j*100))+int(other.get('row_capacity',100))) for j,other in enumerate(zones) if j!=i]
        required=max(cap,rows+1)
        collides=any(base<b and base+required>a for a,b in occupied)
        is_new='row_base' not in z and any(base<b and base+cap>a for a,b in occupied)
        if collides or is_new:
            new_base=cursor;cursor+=required
            if remap and 'row_base' in z:remap(base,cap,new_base)
            base=new_base
        z.update(row_base=base,row_capacity=required,rows=rows,cols=cols,offset_x_mm=ox,offset_y_mm=oy)
        cursor=max(cursor,base+required)
