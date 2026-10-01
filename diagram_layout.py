"""Grouped, naturally ordered string → MPPT → inverter diagrams."""
from project_validation import natural

def arrange(nodes,links,sizes,gap_x=260,gap_y=45):
    incoming={key:[] for key in nodes}
    for link in links:
        if link.get('auto') and link['a'] in nodes and link['b'] in nodes:incoming[link['b']].append(link['a'])
    inverters=sorted((k for k in nodes if k.startswith('inv::')),key=natural)
    widths=[max((sizes[k][0] for k in nodes if k.startswith(prefix)),default=280) for prefix in ('str::','mppt::','inv::')]
    xs=[widths[0]/2]
    for i in (1,2):xs.append(xs[-1]+widths[i-1]/2+gap_x+widths[i]/2)
    group_width=sum(widths)+2*gap_x
    groups=[];used=set()
    for inv in inverters:
        positions={};cursor=0.;mppts=sorted(set(incoming[inv]),key=natural)
        for mppt in mppts:
            strings=sorted(set(incoming[mppt]),key=natural)
            strings_h=sum(sizes[k][1] for k in strings)+gap_y*max(0,len(strings)-1)
            height=max(sizes[mppt][1],strings_h)
            sy=cursor+(height-strings_h)/2
            for key in strings:positions[key]=(xs[0],sy+sizes[key][1]/2);sy+=sizes[key][1]+gap_y
            positions[mppt]=(xs[1],cursor+height/2);cursor+=height+gap_y
        height=max(cursor-gap_y,sizes[inv][1])
        positions[inv]=(xs[2],height/2);used.update(positions);groups.append((positions,height))
    positions={};top=100.
    for row in range(0,len(groups),2):
        for col,(group,height) in enumerate(groups[row:row+2]):
            positions.update({k:(x+50+col*(group_width+100),y+top) for k,(x,y) in group.items()})
        top+=max(height for _,height in groups[row:row+2])+130
    # Unassigned strings and custom devices remain visible in a separate lower row.
    extras=sorted((key for key in nodes if key not in used),key=natural)
    x=50.;height=0.
    for key in extras:
        w,h=sizes[key]
        if x>50 and x+w>2*group_width+150:top+=height+gap_y;x=50;height=0
        positions[key]=(x+w/2,top+h/2);x+=w+60;height=max(height,h)
    return positions

def group_bounds(nodes,sizes):
    groups={}
    for key,node in nodes.items():
        if key.startswith('inv::'):owner=key[5:]
        elif key.startswith('mppt::'):owner=key.split('::')[1]
        else:continue
        groups.setdefault(owner,[]).append(key)
    return groups
