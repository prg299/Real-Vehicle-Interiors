"""Build diagnostic contact sheets from native screenshots; no generated artwork."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
from PIL import Image, ImageDraw, ImageFont


def native_gallery(args):
    """Show every KI5 variant using unchanged originals from one frozen payload."""
    if not args.package_manifest or not args.inventory:
        raise ValueError('Native gallery requires --package-manifest and --inventory')
    payload = {key.replace('\\', '/'): value.lower() for key, value in
               json.loads(args.package_manifest.read_text()).items()}
    payload_id = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    families = [row for row in json.loads(args.inventory.read_text()) if not row['plainFinish']]
    all_supported = {script: row['family'] for row in families for script in row['scripts']}
    assert len(all_supported) == 107 and len(families) == 14, 'KI5 inventory changed; review expected scope'
    expected = {row['representative']: row['family'] for row in families} if args.representatives_only else all_supported
    expected_count = len(expected)
    frames = {}
    interrupted = None
    if args.interrupted_run_receipt:
        interrupted = json.loads(args.interrupted_run_receipt.read_text('utf-8-sig'))
        assert interrupted['kind'] == 'native' and interrupted['exitCode'] == 137
        assert Path(interrupted['cwd']).resolve() == Path(__file__).resolve().parents[1]
    for ledger in args.native_ledger:
        if (ledger.parent/'native-feature-tests.json').exists():
            report = json.loads((ledger.parent/'native-feature-tests.json').read_text())
            assert report['status'] == 'passed' and report['cameraMode'] == 'native deferred pan', ledger
        else:
            assert interrupted, 'Missing completed native report or explicit interruption receipt'
        provenance = json.loads((ledger.parent/'capture-package.json').read_text())
        assert provenance['sha256'] == payload_id and provenance['files'] == payload, ledger
        for line in ledger.read_text().splitlines():
            row = json.loads(line)
            if row['state'] != 'furnished-high':
                continue
            assert row['capturePackageSha256'] == payload_id, 'Mixed-payload gallery frame'
            assert row['script'] in all_supported and row['family'] == all_supported[row['script']], row['script']
            if row['script'] not in expected:
                continue
            assert row['native'] and row['profileNative'] and not row['plain'] and not row['profilePlain'], row['script']
            assert not row.get('shaderError'), row['script']
            assert 'nativePan=true' in row['framingReceipt']['camera'] and 'pose' in row, 'Unverified capture camera/pose'
            image = Path(row['image'])
            assert image.is_file(), image
            assert row['heading'] in ('E', 'N', 'S', 'W'), row['heading']
            frames[row['script'], row['heading']] = row
    missing = [(script, heading) for script in expected for heading in ('E', 'N', 'S', 'W')
               if (script, heading) not in frames]
    if missing and not interrupted:
        raise ValueError(f'KI5 gallery incomplete: {len(missing)} missing views; first: {missing[:8]}')
    if missing and interrupted:
        expected = {script: family for script, family in expected.items()
                    if all((script, heading) in frames for heading in ('E', 'N', 'S', 'W'))}
        assert expected, 'Interrupted run has no complete four-side vehicle set'
        expected_count = len(expected)
    for script in expected:
        poses = [frames[script, heading]['pose'] for heading in ('E', 'N', 'S', 'W')]
        for i, left in enumerate(poses):
            for right in poses[i+1:]:
                dot = (left['forwardX']*right['forwardX']+left['forwardY']*right['forwardY']) / (
                    (left['forwardX']**2+left['forwardY']**2)*(right['forwardX']**2+right['forwardY']**2))**.5
                assert dot < .95, 'Repeated physical pose: '+script
    out = args.audit/('gallery-partial' if missing else 'gallery')
    photos = out/'images'
    photos.mkdir(parents=True, exist_ok=True)
    thumbnails = out/'thumbnails'
    thumbnails.mkdir(exist_ok=True)
    cards, records = [], []
    family_titles = {}
    for script, family in expected.items():
        display = frames[script, 'E'].get('name', script)
        family_titles[family] = frames[script, 'E'].get('familyTitle', family)
        views = []
        for heading in ('E', 'N', 'S', 'W'):
            row = frames[script, heading]
            source = Path(row['image'])
            name = script+'-'+heading+'.png'
            target = photos/name
            shutil.copyfile(source, target)
            thumbnail = thumbnails/(script+'-'+heading+'.jpg')
            with Image.open(source) as frame:
                frame.convert('RGB').resize((640, 360), Image.Resampling.LANCZOS).save(thumbnail, quality=88, optimize=True)
            records.append(dict(script=script, family=family, heading=heading, source=str(source),
                                file='images/'+name, sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                                thumbnail='thumbnails/'+thumbnail.name,
                                thumbnailSha256=hashlib.sha256(thumbnail.read_bytes()).hexdigest()))
            label = html.escape(display+' / '+heading)
            views.append(f'<a href="images/{html.escape(name)}" target="_blank"><img loading="lazy" '
                         f'src="thumbnails/{html.escape(thumbnail.name)}" alt="{label}"><span>{heading}</span></a>')
        cards.append(f'<article data-family="{html.escape(family)}" data-name="{html.escape((display+" "+script).lower())}">'
                     f'<h2>{html.escape(display)}</h2><p>{html.escape(family_titles[family])}</p>'
                     f'<div class="views">{"".join(views)}</div></article>')
    options = ''.join(f'<option value="{html.escape(row["family"])}">{html.escape(family_titles[row["family"]])}</option>'
                      for row in families if row['family'] in family_titles)
    template = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>KI5 interior walls</title>
<style>body{margin:0;background:#17191c;color:#eee;font:16px system-ui}header{padding:24px;position:sticky;top:0;background:#17191cf5;z-index:1;border-bottom:1px solid #42464a}h1{margin:0 0 8px;font-size:26px}header p{margin:6px 0;color:#b9c2c9}input,select{padding:10px;margin:12px 12px 0 0;background:#272b30;color:#eee;border:1px solid #68737d;border-radius:4px;font:inherit}main{padding:20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,640px),1fr));gap:20px}article{padding:16px;background:#24282d;border-radius:6px}article[hidden]{display:none}h2{margin:0;font-size:18px;overflow-wrap:anywhere}article p{color:#b9c2c9;margin:6px 0 12px}.views{display:grid;grid-template-columns:1fr 1fr;gap:8px}.views a{position:relative;color:white}.views img{display:block;width:100%;height:auto}.views span{position:absolute;bottom:4px;left:6px;background:#17191ce8;padding:2px 8px}</style>
<header><h1>KI5 interiors with curved native walls</h1><p>107 variants · 14 body families · four directions per vehicle</p>
<p>Original in-game screenshots. Select any view to open the full image.</p>
<input id="search" type="search" placeholder="Find a vehicle" aria-label="Find a vehicle">
<select id="family" aria-label="Body family"><option value="">All body families</option>OPTIONS</select>
<p id="count">107 vehicles shown</p></header><main>CARDS</main>
<script>const search=document.querySelector('#search'),family=document.querySelector('#family');function filter(){let count=0;for(const card of document.querySelectorAll('article')){card.hidden=Boolean((family.value&&card.dataset.family!==family.value)||!card.dataset.name.includes(search.value.toLowerCase()));if(!card.hidden)count++;}document.querySelector('#count').textContent=count+' vehicles shown';}search.addEventListener('input',filter);family.addEventListener('change',filter);</script></html>'''
    if args.representatives_only:
        template = template.replace('107 variants · 14 body families · four directions per vehicle',
                                    'All 14 body families · one representative per family · four directions each')
        template = template.replace('107 vehicles shown', '14 vehicles shown')
    if missing:
        summary = f'Partial preview: {len(family_titles)} of 14 body families · four directions each'
        template = template.replace('All 14 body families · one representative per family · four directions each', summary)
        template = template.replace('107 variants · 14 body families · four directions per vehicle', summary)
        template = template.replace('14 vehicles shown', f'{expected_count} vehicles shown').replace('107 vehicles shown', f'{expected_count} vehicles shown')
        template = template.replace('Original in-game screenshots.', 'Capture stopped by the memory guard. Original in-game screenshots.')
    if args.review_note:
        template = template.replace('<input id="search"', ''.join('<p>'+html.escape(note)+'</p>' for note in args.review_note)+'<input id="search"')
    (out/'index.html').write_text(template.replace('OPTIONS', options).replace('CARDS', ''.join(cards)), encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps(dict(
        capturePackageSha256=payload_id, variants=expected_count, families=len(family_titles), originals=records,
        incomplete=bool(missing), missingViews=missing, interruption=interrupted, reviewNotes=args.review_note,
        scope='Native renderer captures; gallery export is not a visual acceptance receipt'), indent=2)+'\n')
    markdown = ['# KI5 interior walls', '',
                ('All 14 body families, one representative each. Four original in-game views per vehicle.'
                 if args.representatives_only else 'All 107 supported KI5 variants. Four original in-game views per vehicle.'), '']
    if missing:
        markdown[2] = f'Partial preview: {len(family_titles)} of 14 KI5 body families, four original views each. The memory guard stopped further captures.'
    for note in args.review_note:
        markdown += [note, '']
    for script, family in expected.items():
        display = frames[script, 'E'].get('name', script)
        markdown += ['## '+display, '', family_titles[family], '']
        for heading in ('E', 'N', 'S', 'W'):
            source = (photos/(script+'-'+heading+'.png')).resolve()
            markdown += ['![%s / %s](%s)' % (display, heading, source.as_posix()), '']
    (out/'gallery.md').write_text('\n'.join(markdown), encoding='utf-8')
    print(f'KI5 gallery: {expected_count} variants, {len(records)} unchanged native views: {out/"index.html"}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit',type=Path)
    parser.add_argument('--detail',action='store_true',help='One variant per page, four native-size frames without rescaling')
    parser.add_argument('--native-ledger', action='append', type=Path, help='Current native-body frames.jsonl; repeat for batches')
    parser.add_argument('--package-manifest', type=Path, help='Frozen package SHA-256 manifest for native gallery')
    parser.add_argument('--inventory', type=Path, help='Source family inventory with plainFinish policy')
    parser.add_argument('--representatives-only', action='store_true', help='All 14 KI5 body families, one source representative each')
    parser.add_argument('--interrupted-run-receipt', type=Path, help='Exit137 coordinator receipt; export only complete available sets with a partial banner')
    parser.add_argument('--review-note', action='append', default=[], help='Visible review finding or coverage boundary')
    args=parser.parse_args()
    if args.native_ledger:
        native_gallery(args)
        return
    rows=[json.loads(line) for line in (args.audit/'variants.jsonl').read_text().splitlines()]
    rows=list({row['number']:row for row in rows}.values())
    rows.sort(key=lambda row:row['number'])
    factory = bool(rows) and 'factory' in rows[0]
    if args.detail and not factory:parser.error('--detail requires a four-heading factory audit')
    columns, row_height = ((2, 752) if args.detail else ((4, 330) if factory else (5, 280)))
    cell_width = 1280 if args.detail else 1920 // columns
    page_width=cell_width*columns
    per_page=1 if args.detail else 4
    out=args.audit/('detail-sheets' if args.detail else 'contact-sheets');out.mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',19)
    reviewed=set()
    review_log=args.audit/'visual-review.jsonl'
    if review_log.exists():
        for line in review_log.read_text('utf-8-sig').splitlines():
            reviewed.update(json.loads(line).get('variants',[]))
    issues={}
    issue_log=args.audit/'visual-issues.jsonl'
    if issue_log.exists():
        for line in issue_log.read_text('utf-8-sig').splitlines():
            entry=json.loads(line);issues[entry['id']]=entry
    flagged={entry['variant'] for entry in issues.values() if not entry['status'].startswith('resolved')}
    renderer_mtime=Path(__file__).stat().st_mtime
    pages=[]
    for start in range(0,len(rows),per_page):
        group=rows[start:start+per_page]
        page_number=group[0]['number']+1 if args.detail else start//per_page+1
        target=out/('page-%03d.jpg'%page_number)
        numbers=[row['number'] for row in group]
        state='flagged' if any(n in flagged for n in numbers) else ('reviewed' if all(n in reviewed for n in numbers) else 'pending')
        page=dict(page=str(target),variants=[row['name'] for row in group],numbers=numbers,review=state)
        if target.exists():
            with Image.open(target) as previous:complete=previous.size==(page_width,row_height*(2 if args.detail else len(group)))
            newest_input=max(renderer_mtime,max(Path(p).stat().st_mtime for row in group for p in row['images']))
            if complete and target.stat().st_mtime>=newest_input:
                pages.append(page);continue
        sheet=Image.new('RGB',(page_width,row_height*(2 if args.detail else len(group))),(22,24,27));draw=ImageDraw.Draw(sheet)
        for row_index,row in enumerate(group):
            y=row_index*row_height
            if not args.detail:
                draw.text((10,y+4),f"{row['number']:03}  {row['name']}   {row['family']}",font=font,fill='white')
            images=row['images']
            order=[next(path for path in images if path.endswith(('-' if factory else '-interior-')+heading+'.png')) for heading in ('e','n','s','w')]
            if not factory:order.append(next(path for path in images if path.endswith('-outside.png')))
            for col,path in enumerate(order):
                tile_x=(col%columns)*cell_width
                tile_y=(col//columns)*row_height if args.detail else y
                with Image.open(path) as source:
                    # Keep the complete frame: clipped geometry remains apparent.
                    source=source.convert('RGB')
                    if not args.detail:source.thumbnail((cell_width,row_height-64))
                    else:assert source.size==(1280,720),('native detail frame size changed',path,source.size)
                    sheet.paste(source,(tile_x,tile_y+31))
                if args.detail:
                    draw.text((tile_x+8,tile_y+4),f"{row['number']:03} {row['name']} "+('E','N','S','W','Closed exterior')[col],font=font,fill='white')
                else:draw.text((tile_x+8,tile_y+row_height-30),('E','N','S','W','Closed exterior')[col],font=font,fill=(190,200,210))
        sheet.save(target,quality=96)
        pages.append(page)
    (out/'index.json').write_text(json.dumps(pages,indent=2))
    print(f'{len(rows)} variants, {len(pages)} pages: {out}')


if __name__=='__main__':main()
