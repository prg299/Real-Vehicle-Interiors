"""Measured cargo/service fit-outs appended after released furniture slot IDs.

Profiles sharing a body reuse shells and walk grids. Only their factory furniture,
loot and optional attendant seats vary. Existing saved slots are never relocated.
"""
import make_vehicles as mv

SIZES = {
    'safe': (.60,.52,.90), 'parcels': (.60,.50,.85),
    'medlocker': (.50,.32,.98), 'medbench': (1.10,.40,.80),
    'equipmentrack': (.60,.32,.98), 'metalcase': (.52,.52,.80), 'stretcher': (1.50,.55,.55),
    'workbench': (.90,.40,.78), 'kitchen': (1.0,.52,.92), 'fridge': (.52,.52,.88),
}

# Native Build 42 distribution names and Base item IDs. The starter quantities are
# deliberately small: fillFurniture adds them first, then capacity-checks native rolls.
# A role describes the actual signwritten business, independently of the vehicle body.
ROLE_SUPPLIES = {
    'medical': ('MedicalStorageTools', [('Bandage',6),('Disinfectant',1),('AlcoholWipes',3)]),
    'bank': ('BankDeposit', [('MoneyBundle',6),('Money',10)]),
    'security': ('PoliceTools', [('WalkieTalkie4',1),('Torch',1),('Battery',2)]),
    'swat': ('ArmyStorageElectronics', [('WalkieTalkie4',1),('Torch',1),('Battery',2)]),
    'passenger': (None, [('WaterBottle',1),('BathTowel',1)]),
    'prisoner': (None, []),
    'radio': ('CrateElectronics', [('ElectricWire',1),('Battery',2)]),
    'electrical': ('CrateElectronics', [('ElectricWire',2),('Screwdriver',1),('ElectronicsScrap',3)]),
    'mechanic': ('CrateMechanics', [('Wrench',1),('Screwdriver',1),('LugWrench',1)]),
    'carpentry': ('CrateCarpentry', [('Hammer',1),('Saw',1),('NailsBox',1)]),
    'metalwork': ('CrateMetalwork', [('BlowTorch',1),('WeldingRods',1)]),
    'blacksmith': ('CrateBlacksmithing', [('Hammer',1),('Tongs',1)]),
    'masonry': ('CrateMasonry', [('HandShovel',1),('Bucket',1)]),
    'painting': ('CratePaint', [('Paintbrush',1),('PaintWhite',1)]),
    'plumbing': ('CrateMetalPipes', [('PipeWrench',1),('MetalPipe',2)]),
    'locksmith': ('ToolStoreKeymaking', [('Key_Blank',3),('Screwdriver',1)]),
    'work': ('CrateTools', [('Screwdriver',1),('Wrench',1),('DuctTape',1)]),
    'garden': ('GardenStoreTools', [('HandShovel',1),('WateredCan',1)]),
    'florist': ('GardenStoreMisc', [('RoseBagSeed',2),('MarigoldBagSeed',2),('WateredCan',1)]),
    'laundry': ('CrateLinens', [('Sheet',3),('BathTowel',3)]),
    'tailoring': ('CrateTailoring', [('SewingKit',1),('Thread',2),('Scissors',1)]),
    'leather': ('CrateLeather', [('LeatherStrips',3),('Thread',2),('Scissors',1)]),
    'craft': ('CratePottery', [('ClayTool',1),('Brush',1)]),
    'glasswork': ('GlassWorkshopTools', [('GlassBlowingPipe',1),('CeramicCrucibleSmall',1),('Glasses_SafetyGoggles',1)]),
    'pestcontrol': (None, [('RatPoison',2),('TrapMouse',3),('Gloves_Dish',1)]),
    # Cylinders are real placed Floor inventory, not cupboard/rack contents.
    'propane': (None, [('Wrench',1),('Gloves_LeatherGloves',1)]),
    'water': ('CrateWaterBottle', [('WaterBottle',6)]),
    'eggs': ('CrateEggs', [('EggCarton',3)]),
    'coldfood': ('ButcherFreezer', [('Steak',2),('Chicken',1)]),
    'seafood': ('ButcherFish', [('Shrimp',4),('Salmon',2)]),
    'ham': ('ButcherSmoked', [('Ham',1),('Bacon',2)]),
    'catering': ('KitchenDishes', [('Bowl',2),('Plate',2)]),
    'beer': ('CrateBeer', [('BeerCan',4),('BeerBottle',2)]),
    'liquor': ('CrateLiquor', [('Whiskey',2)]),
    'coffee': ('CrateCoffee', [('Coffee2',3)]),
    'softdrinks': ('CrateSodaBottles', [('PopBottle',4)]),
    'cereal': ('CrateCereal', [('Cereal',3)]),
    'food': ('CrateCannedFood', [('TinnedBeans',2),('CannedCorn',2),('Crisps',2)]),
    'snacks': ('CrateChips', [('Crisps',6)]),
    'postal': ('PostOfficeParcels', [('Parcel_Small',2),('Parcel_Medium',1)]),
    'newspaper': ('PostOfficeNewspapers', [('Newspaper_New',6)]),
    'library': ('LibraryBooks', [('Book',6),('BookCarpentry1',1)]),
    'delivery': ('PostOfficeParcels', [('Parcel_Small',2),('Parcel_Medium',1)]),
}

# More specific names precede shared trade words (e.g. blacksmith before smith,
# airport catering before food, and radio before electronics). Shortened native
# script names and the KI5 spelling variants are intentional aliases.
ROLE_NAMES = (
    ('radio', ('radio',)),
    ('library', ('library',)), ('newspaper', ('herald',)), ('postal', ('postal','mail')),
    ('catering', ('catering','hospitality','southeasternhosp')),
    ('coldfood', ('butcher',)), ('seafood', ('marinebites',)), ('ham', ('pennsham',)),
    ('beer', ('beer','genuine','tastethebrew')), ('liquor', ('distil','knoxdisti','scarlet')),
    ('coffee', ('brewster',)), ('softdrinks', ('citr8','citruswave')),
    ('cereal', ('cereal','sunballz')), ('water', ('oldmill',)), ('eggs', ('ovofarm',)),
    ('snacks', ('perfick',)), ('food', ('greenes','zippee','plonki','spiffo')),
    ('propane', ('propane','knobcreek')),
    ('florist', ('florist','randys','randisplants')),
    ('garden', ('garden','landscap','treybaines')), ('laundry', ('laundry',)),
    ('tailoring', ('tailor','smartcut','smartkut')), ('leather', ('leather',)),
    ('craft', ('brushandclay','craftsupplies')),
    ('glasswork', ('zenith','glass')),
    ('pestcontrol', ('bugwiper',)), ('locksmith', ('locksmith',)),
    ('electrical', ('electr','lectro','telecom','knoxcom','voltmojo')),
    ('mechanic', ('mechanic','repair','motorshop','plattauto','korshunov','transit')),
    ('blacksmith', ('blacksmith',)), ('painting', ('paint',)),
    ('masonry', ('masonry','stoneworks')), ('plumbing', ('plumb','unclog')),
    ('metalwork', ('metal','fabrication','riversidefab','schwab','jones','massgenfac')),
    ('carpentry', ('wood','carpent','mccoy','micheles','jorgensen')),
    ('work', ('construct','builder','beckman','kerrhomes','utility','fossoil')),
)
WORK_ROLES = {'radio','electrical','mechanic','carpentry','metalwork','blacksmith',
              'masonry','painting','plumbing','locksmith','glasswork','work'}
COLD_ROLES = {'coldfood','seafood','ham','eggs'}


def role_for(name, key):
    n = name.lower()
    if name in ('Base.VanAmbulance','Base.86fordE150med','Base.90fordF350ambulance'): return 'medical'
    if key == 'F700Bank': return 'bank'
    if 'swat' in n: return 'swat'
    if n.endswith(('e150pd','e150ksp','e150so')): return 'security'
    if 'vanseats_prison' in n: return 'prisoner'
    # Named leisure/band vans use seats and open floor, not delivery freight.
    # Their original trunk inventory (including DND's dog/trip supplies) stays native.
    if name in ('Base.86fordE150mm','Base.86fordE150creatureCruiser','Base.86fordE150dnd',
                'Base.86fordE150mesmerWagon','Base.86fordE150quantumVessel',
                'Base.86fordE150theLadyDelighter','Base.86fordE150valkyriesSpear'):
        return 'passenger'
    if key in ('VanillaPassengerVan','E150Windows'): return 'passenger'
    for role, names in ROLE_NAMES:
        if any(s in n for s in names): return role
    return 'delivery'


def use_for(role):
    distribution, supplies = ROLE_SUPPLIES[role]
    use = dict(loot={}, stock={})
    def fill(pieces, distribution, supplies):
        for piece in pieces:
            if distribution: use['loot'][piece] = distribution
            else: use['loot'].pop(piece, None)
            use['stock'][piece] = [['Base.'+name,count] for name,count in supplies]
    fill(['safe'] if role=='bank' else ['parcels','equipmentrack','metalcase','medlocker','workbench'],
         distribution, supplies)
    # Seats remain seats, not duplicate tool/food/weapon racks. Only their modest
    # under-seat supplies are populated; prisoner benches intentionally stay empty.
    fill(['medbench'], None, ROLE_SUPPLIES['passenger'][1] if role=='passenger' else [])
    if role=='radio':
        # Real native radio inventory, shown by LooseView on the empty worktop.
        fill(['workbench'], None, [('HamRadio1',1),('Headphones',1),('Battery',2)])
        fill(['medbench'], None, [('Notebook',1),('Pen',1)])
    elif role=='medical':
        fill(['medbench'], None, [('Sheet',1),('Bandage',2)])
    elif role in COLD_ROLES:
        fill(['fridge'], distribution, supplies)
        fill(['equipmentrack','metalcase'], None, [('PaperBag',3),('Twine',1)])
    elif role=='catering':
        fill(['kitchen'], 'KitchenPots', [('Saucepan',1),('KitchenKnife',1),('Plate',2)])
        fill(['fridge'], 'FridgeGeneric', [('Butter',1),('Milk',1),('EggCarton',1)])
    return use


def layout(spec, base, role):
    half=spec['box']['x']-.03; rear,front=spec['box']['z']; floor=base['floorY']
    result=[]; seat_ids=[]

    def add(piece,wall,at,seats=0):
        width,depth,height=SIZES[piece]
        # A low roof still needs cabinet headroom; use the existing drawer unit.
        if floor+height>spec['ceiling']-.02:
            if piece in ('medlocker','equipmentrack'):piece='metalcase';width,depth,height=SIZES[piece]
        if wall in ('left','right'):
            x,z=(half if wall=='left' else -half),at
            if z-width/2<rear+.09-1e-6 or z+width/2>front-.05+1e-6:return False
        else:
            x,z=at,front-.03
            if abs(x)+width/2>half:return False
        spot=dict(wall=wall,x=round(x,3),z=round(z,3),length=width,depth=depth,
                  default=piece,factory=True,pieces=[piece])
        # All dimensions are in passenger space. Check the actual 3D footprints.
        box=mv.footprint(spot)
        for other in result:
            if mv.overlap(box,mv.footprint(other),.005):return False
        if seats:
            ids=[]
            for _ in range(seats):
                if len(seat_ids)>=len(base.get('extraSeats',[])):break
                sid=base['extraSeats'][len(seat_ids)];seat_ids.append(sid);ids.append(sid)
            if ids:spot['seats']=ids
        result.append(spot);return True

    if role=='medical':
        add('stretcher','left',rear+.90,1)
        add('medbench','right',rear+.93,2)
        # Cabinets across the bulkhead; longer ambulances get additional side banks.
        for x in (-.27,.27):add('medlocker','front',x)
        for wall in ('left','right'):
            for at in (front-.64,front-1.19):add('medlocker',wall,at)
    elif role=='swat':
        per_bench=min(2,len(base.get('extraSeats',[]))//2)
        for wall in ('left','right'):assert add('medbench',wall,rear+.76,per_bench)
        for wall,piece in (('left','metalcase'),('right','equipmentrack')):
            at=front-.39
            while at-SIZES[piece][0]/2>=rear+1.34:
                add(piece,wall,at);at-=.68
    elif role in ('passenger','prisoner'):
        per_bench=min(2,len(base.get('extraSeats',[]))//2)
        for wall in ('left','right'):add('medbench',wall,front-.68,per_bench)
        # Keep the rear loading/standing area usable. Passenger vans are not
        # warehouses, and a prison transport must not expose stocked tool racks.
    elif role=='propane':
        assert add('metalcase','front',0)
    elif role in WORK_ROLES:
        assert add('workbench','left',front-.53)
        add('equipmentrack','left',rear+.45)
        add('equipmentrack','right',front-.39)
        # Crew/operator rest seat with actual passenger IDs, clear of the door.
        add('medbench','right',rear+.76,min(2,len(base.get('extraSeats',[]))))
    elif role=='library':
        for wall in ('left','right'):
            at=front-.39
            while at-.30>=rear+.12:
                add('equipmentrack',wall,at);at-=.68
    elif role=='catering' or role in COLD_ROLES:
        if role=='catering':
            assert add('kitchen','left',front-.57)
            assert add('fridge','left',rear+.47)
        else:
            for at in (front-.35,rear+.47):add('fridge','left',at)
        # Shallow dry-storage side keeps the aisle usable in the narrow vans.
        for at in (front-.39,rear+.47):add('equipmentrack','right',at)
    else:
        left='safe' if role=='bank' else ('metalcase' if role in ('security','pestcontrol') else 'parcels')
        right='safe' if role=='bank' else ('equipmentrack' if role in ('security','pestcontrol','florist','garden') else 'parcels')
        # Narrow vans retain a full walking aisle by using shallow racking on one side.
        if 2*half-SIZES[left][1]-SIZES[right][1]<.31:right='equipmentrack'
        for wall,piece in (('left',left),('right',right)):
            step_van=spec['key']=='VanillaStepVan'
            at=front-(.35 if step_van else .39)
            while at-SIZES[piece][0]/2>=rear+(.12 if step_van else .38):
                add(piece,wall,at);at-=(.65 if step_van else .68)
        if role not in ('bank',):
            # Short front cross-wall cabinet fills the gap without blocking the rear doors.
            add('metalcase','front',0)
    assert result,(spec['key'],role)
    if role=='medical':assert result[0]['default']=='stretcher' and any(s['default']=='medbench' for s in result)
    if role=='swat':assert len([s for s in result if s['default']=='medbench'])==2 and seat_ids
    return result,seat_ids


def floor_cargo(spec, base, spots, role):
    """Small side rows of real cylinders, clear of the measured room solids.

    The native harness must confirm the unscaled world model fits this planned
    34cm square and the measured roof. No new furniture or display-only stock.
    """
    if role!='propane':return []
    half=spec['box']['x']-.03;rear,front=spec['box']['z']
    hx=hz=.17;gap=.025;pitch=2*hz+.04
    solids=[mv.footprint(s) for s in spots]
    solids += [(min(w['x']),max(w['x']),min(w['z']),max(w['z'])) for w in base.get('wheelWells',[])]
    solids += [(b['x1'],b['x2'],b['z1'],b['z2']) for b in base.get('blocked',[])]
    result=[]
    for side in (-1,1):
        x=round(side*(half-hx-gap),3)
        assert abs(x)-hx>=.175,(spec['key'],'propane center aisle')
        intervals=[(rear+.06+hz,front-.06-hz)]
        # Subtract entire inflated obstacle intervals. A discrete point scan can
        # miss the small valid gap between a cabinet and a native wheel cover.
        for x0,x1,z0,z1 in solids:
            if x-hx>=x1+gap or x+hx<=x0-gap:continue
            cut0,cut1=z0-hz-gap,z1+hz+gap
            clear=[]
            for lo,hi in intervals:
                if cut1<=lo or cut0>=hi:clear.append((lo,hi))
                else:
                    if lo<cut0:clear.append((lo,min(hi,cut0)))
                    if cut1<hi:clear.append((max(lo,cut1),hi))
            intervals=clear
        count=0
        for lo,hi in sorted(intervals,reverse=True):
            if hi<lo:continue
            n=min(3-count,1+int((hi-lo)/pitch))
            if n<=0:break
            center=(lo+hi)/2
            for index in range(n):
                z=round(center+(index-(n-1)/2)*pitch,3)
                box=(x-hx,x+hx,z-hz,z+hz)
                assert -half<=box[0]<box[1]<=half and rear<=box[2]<box[3]<=front,(spec['key'],'propane outside room',box)
                assert all(not mv.overlap(box,b,0) for b in solids),(spec['key'],'propane intersects solid',box)
                assert all(not mv.overlap(box,(c['x']-hx,c['x']+hx,c['z']-hz,c['z']+hz),0) for c in result)
                result.append(dict(t='Base.PropaneTank',x=x,z=z,r=0,hx=hx,hz=hz))
            count+=n
    assert 2<=len(result)<=6,(spec['key'],'propane floor count',len(result))
    return result


def append_profiles(spec, base, lines):
    groups={}
    for name in spec['vehicles']:groups.setdefault(role_for(name,spec['key']),[]).append(name)
    for role,names in groups.items():
        spots,seats=layout(spec,base,role)
        cargo=floor_cargo(spec,base,spots,role)
        depths={wall:max([s['depth'] for s in spots if s['wall']==wall] or [0]) for wall in ('left','right')}
        aisle=round((depths['right']-depths['left'])/2,3)
        # Match the production 15cm character clearance. A nominal 30cm gap
        # can vanish after the 25mm floor grid is rasterized.
        half=spec['box']['x']-.03;rear,front=spec['box']['z']
        for step in range(int((front-rear-1.03)/.025)):
            z=rear+.23+step*.025
            for s in spots:
                x0,x1,z0,z1=mv.footprint(s)
                assert not (x0-.15<=aisle<=x1+.15 and z0-.15<=z<=z1+.15),(spec['key'],role,'blocked aisle',s)
        assert 2*half-depths['left']-depths['right']>=.35,(spec['key'],role,'aisle narrower than grid-safe clearance')
        # Shallow copy immutable geometry, copy arrays we extend. The released slots
        # retain both IDs and coordinates, so a loaded player's furnishings stay put.
        lines += ['', 'do', '    local fitted = {}', '    for k,v in pairs(profile) do fitted[k]=v end',
                  '    fitted.legacySpotCount = #profile.spots',
                  '    fitted.spots = {}', '    for i,s in ipairs(profile.spots) do fitted.spots[i]=s end',
                  '    fitted.extraSeats = {}', '    for i,s in ipairs(profile.extraSeats or {}) do fitted.extraSeats[i]=s end',
                  '    fitted.factoryLayout = "cargo-service-1"',
                  '    fitted.factoryRole = '+mv.lua(role),
                  '    fitted.factoryUse = '+mv.lua(use_for(role)),
                  '    fitted.aisleX = '+str(aisle),
                  '    for _,s in ipairs('+mv.lua(spots)+') do fitted.spots[#fitted.spots+1]=s end']
        if cargo:lines.append('    fitted.factoryFloor = '+mv.lua(cargo))
        for name in names:lines.append('    MELens.Profiles['+mv.lua(name)+'] = fitted')
        lines.append('end')
