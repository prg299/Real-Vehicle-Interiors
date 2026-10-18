# Generates ME: LENS' source art with ChatGPT's image model (the local wrapper, see the
# user's global instructions): seamless material textures for tools-src/blender/rv_kit.py
# and the RV furniture inventory icons. Runs one image at a time (the wrapper collects
# new images by time). Existing files are kept; delete one to make it again.
#   .\tools-src\art\generate.ps1              everything missing
#   .\tools-src\art\generate.ps1 -Only quilt  one image
param([string[]]$Only = @())

$ErrorActionPreference = 'Stop'
$wrapper = Join-Path $env:USERPROFILE '.claude\tools\chatgpt-image.ps1'
$root = $PSScriptRoot
$textures = Join-Path $root 'textures'
$icons = Join-Path $root 'icons'
New-Item -ItemType Directory -Force -Path $textures, $icons | Out-Null

$style = 'Hand-painted, softly painterly style like the isometric art of the game Project Zomboid: muted, slightly desaturated colours, matte, flat even lighting, no shadows, no highlights, no text, no border, the texture fills the whole square image.'
$tex = [ordered]@{
    wood_light   = "Seamless tileable square texture of light honey oak wood grain for game furniture: warm light-brown tones with gentle, subtle grain streaks running horizontally, no knots. $style"
    wood_dark    = "Seamless tileable square texture of dark walnut wood grain for game furniture: deep muted brown with gentle, subtle grain streaks running horizontally, no knots. $style"
    birch        = "Seamless tileable square texture of pale birch wood veneer for cabinet doors: light creamy beige-tan with a very subtle, fine horizontal grain. $style"
    quilt        = "Seamless tileable square texture of a homemade patchwork quilt for a bed blanket: small squares of dusty rose-red, faded cream and soft slate blue fabrics joined by simple stitched seams, slightly worn. $style"
    sheet        = "Seamless tileable square texture of plain off-white cotton bed sheet fabric with a very subtle weave and faint soft wrinkles. $style"
    mattress     = "Seamless tileable square texture of old mattress ticking fabric: off-white with faint thin pale grey-blue stripes running vertically and a very subtle weave, slightly worn. $style"
    vinyl        = "Seamless tileable square texture of 1950s dinette upholstery vinyl: muted teal-blue with a subtle fine leather-like grain, no seams. $style"
    laminate     = "Seamless tileable square texture of a 1950s retro kitchen countertop laminate: pale cream background with a faint scattered pattern of small grey and pale blue boomerang shapes. $style"
    enamel       = "Seamless tileable square texture of off-white enamel painted metal like an old refrigerator: warm off-white with faint scuffs, tiny speckles and a slight yellowed grime. $style"
    steel        = "Seamless tileable square texture of brushed stainless steel: soft light grey with fine horizontal brushing, no reflections. $style"
    darkmetal    = "Seamless tileable square texture of old dark brown-grey painted metal with light scuffs and wear. $style"
    floor_planks = "Seamless tileable square texture of a wooden plank floor seen from directly above: narrow medium-brown planks running vertically with staggered end joints, gentle grain and slight colour variation between planks, thin dark gaps between planks. $style"
    wall_paint   = "Seamless tileable square texture of an off-white painted interior wall: warm cream-white with very faint uneven paint strokes and subtle grime. $style"
    lino         = "Seamless tileable square texture of a small black and cream checkered linoleum floor, worn and slightly yellowed. $style"
    cardboard    = "Seamless tileable square texture of a plain brown corrugated cardboard box side: light tan-brown kraft paper with faint vertical flutes showing through and a few small scuffs, no printing, no labels, no tape. $style"
    busvinyl     = "Seamless tileable square texture of 1980s school bus seat vinyl upholstery: muted dark forest green with a fine leather-like grain and faint wear, no seams, no stitching. $style"
    plywood      = "Seamless tileable square texture of plain sanded plywood sheet lining the inside of a box truck: pale tan plywood with soft wavy grain, a few small knots and light scuffs, no seams. $style"
    rubberfloor  = "Seamless tileable square texture of a school bus floor seen from above: dark charcoal grey ribbed rubber matting with fine evenly spaced parallel ribs running vertically, slightly worn and dusty. $style"
    diamondplate = "Seamless tileable square texture of aluminium diamond plate (tread plate) like the metal covers over a camper's wheel wells: light grey metal with a regular, evenly spaced pattern of small raised diagonal ridges in a herringbone arrangement, soft and slightly worn, no rust. $style"
}

$iconStyle = 'Inventory item icon for the game Project Zomboid, in the game''s own hand-painted item icon style: the object alone, seen in a three-quarter view from slightly above, soft shading, muted colours, a thin darker outline, centered and filling most of the image, on a fully transparent background (real alpha transparency: no backdrop colour, no glow, no vignette), no text, no ground shadow.'
$ico = [ordered]@{
    bed      = "A simple single bed: a low plain light-wood base box with a thick plain off-white mattress with faint grey-blue stripes lying on top. No headboard, no footboard, no posts, no blanket, no pillow, no sheets. $iconStyle"
    dinette  = "A small 1950s camper dinette: two teal-blue vinyl benches with backrests facing each other and a cream laminate table on a chrome leg between them. $iconStyle"
    kitchen  = "A compact camper kitchenette counter: light birch cabinet doors, a cream laminate countertop with a two-burner stove and a small steel sink with a faucet. $iconStyle"
    fridge   = "A small off-white 1950s camper refrigerator with rounded edges, a small freezer door on top and chrome handles. $iconStyle"
    cabinet  = "A small wooden cabinet with three drawers, a cream laminate top and chrome drawer pulls. $iconStyle"
    wardrobe = "A narrow dark walnut wooden wardrobe with two tall doors and chrome handles. $iconStyle"
    washroom = "A compact camper washroom cubicle with off-white walls, open at the top, showing a small toilet and a wash basin inside, with a wooden door. $iconStyle"
    heater   = "A small vintage camper propane heater: a dark brown enamel box with a front grille, a small glowing window and copper trim on top. $iconStyle"
    shelf    = "A small open wooden shelving unit for a camper: two light-wood side panels, three wooden boards (a bottom board, one middle shelf and a top board) making two roomy open compartments, a low dark rail along the front edge of the bottom board and the middle shelf, and a dark wood back board, empty. $iconStyle"
    box      = "A single plain brown cardboard moving box, closed with a strip of tape along the top, slightly wider than tall. $iconStyle"
    busseat  = "A single 1980s school bus bench seat: dark green vinyl seat and tall backrest on a grey steel frame with one leg. $iconStyle"
    busseat2 = "Two 1980s school bus bench seats one behind the other: dark green vinyl seats and tall backrests on grey steel frames. $iconStyle"
}

# The shells' flat pixel-art tiles (rv_kit.py, FLAT style: floors and walls as hard pixels, like the
# Viewpoint model packs and the game's own sprites). 128 px, nearest-neighbour: they are repeated across the
# floor and walls, each pixel several screen pixels wide. (The tiles in textures/ came from prompts to this
# effect; the first prompts were not kept, so making one again gives a similar tile, not the same one.)
$pxStyle = 'Chunky pixel art in the style of the isometric tiles of the game Project Zomboid: a coarse visible pixel grid, a few flat colours with light dithered variation, hard pixel edges, no outlines, no gradients, no shadows, no text, seamless and tileable on all sides, the texture fills the whole square image.'
$px = [ordered]@{
    px_floor_planks = "Seamless tileable pixel art tile of a wooden plank floor seen from directly above: warm medium-brown boards running vertically, with darker wood-grain swirls, thin dark gaps between boards and a few staggered end joints. $pxStyle"
    px_truck_floor  = "Seamless tileable pixel art tile of the weathered wooden floor of a box truck seen from directly above: dark grey-brown boards running vertically, worn, with pale scuffs, a few small dark nail heads and short metal strap marks. $pxStyle"
    px_bus_floor    = "Seamless tileable pixel art tile of a school bus floor seen from directly above: near-black charcoal rubber matting with fine evenly spaced parallel ribs running vertically and a few lighter specks of dust. $pxStyle"
    px_wall_cream   = "Seamless tileable pixel art tile of a cream painted wall panelling: plain warm cream vertical panels separated by thin slightly darker tan grooves. $pxStyle"
    px_wall_steel   = "Seamless tileable pixel art tile of corrugated light grey steel wall panels of a box truck: plain flat light grey vertical panels separated by darker grey ribs. $pxStyle"
}

function Make($name, $prompt, $dir, [string[]]$extra = @('-Raw')) {
    if ($Only.Count -gt 0 -and $Only -notcontains $name) { return }
    $path = Join-Path $dir "$name.png"
    if (Test-Path -LiteralPath $path) { Write-Host "have $name"; return }
    Write-Host "generating $name ..."
    try {
        # -Raw: the full-resolution image; icons.py and rv_kit.py do their own cropping and scaling
        & powershell -NoProfile -ExecutionPolicy Bypass -File $wrapper -Prompt $prompt -Out $path @extra | Out-Host
    } catch {
        Write-Host "FAILED $name : $_"
    }
}

foreach ($k in $tex.Keys) { Make $k $tex[$k] $textures }
foreach ($k in $px.Keys) { Make $k $px[$k] $textures @('-Size', '128', '-Pixel') }
foreach ($k in $ico.Keys) { Make "icon_$k" $ico[$k] $icons }
Write-Host 'art done'
