"""Build diagnostic contact sheets from native screenshots; no generated artwork."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit',type=Path)
    parser.add_argument('--detail',action='store_true',help='One variant per page, four native-size frames without rescaling')
    args=parser.parse_args()
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
