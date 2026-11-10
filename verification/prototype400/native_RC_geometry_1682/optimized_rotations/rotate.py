import pya
for angle in range(4):
    layout=pya.Layout();layout.read('/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_zero_junction_crop_1660/crop.gds');top=layout.top_cell();top.name="RotatedCrop"
    top.transform(pya.Trans(angle,False,0,0))
    box=top.bbox()
    # Translate by an integral technology-grid multiple before Magic import.
    dx=((100000-box.left+9)//10)*10;dy=((100000-box.bottom+9)//10)*10
    top.transform(pya.Trans(dx,dy))
    layout.write('/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_optimized_RC_controls_1673'+"/rotation"+str(angle)+".gds")
