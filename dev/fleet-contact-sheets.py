"""Build diagnostic contact sheets from native screenshots; no generated artwork."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit',type=Path)
    args=parser.parse_args()
    rows=[json.loads(line) for line in (args.audit/'variants.jsonl').read_text().splitlines()]
    rows=list({row['number']:row for row in rows}.values())
    rows.sort(key=lambda row:row['number'])
    factory = bool(rows) and 'factory' in rows[0]
    columns, row_height = (4, 330) if factory else (5, 280)
    cell_width = 1920 // columns
    out=args.audit/'contact-sheets';out.mkdir(exist_ok=True)
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
    pages=[]
    for start in range(0,len(rows),4):
        group=rows[start:start+4]
        target=out/('page-%02d.jpg'%(start//4+1))
        numbers=[row['number'] for row in group]
        state='flagged' if any(n in flagged for n in numbers) else ('reviewed' if all(n in reviewed for n in numbers) else 'pending')
        page=dict(page=str(target),variants=[row['name'] for row in group],numbers=numbers,review=state)
        if target.exists():
            with Image.open(target) as previous:complete=previous.size==(1920,row_height*len(group))
            if complete and target.stat().st_mtime>=max(Path(p).stat().st_mtime for row in group for p in row['images']):
                pages.append(page);continue
        sheet=Image.new('RGB',(1920,row_height*len(group)),(22,24,27));draw=ImageDraw.Draw(sheet)
        for row_index,row in enumerate(group):
            y=row_index*row_height
            draw.text((10,y+4),f"{row['number']:03}  {row['name']}   {row['family']}",font=font,fill='white')
            images=row['images']
            order=[next(path for path in images if path.endswith(('-' if factory else '-interior-')+heading+'.png')) for heading in ('e','n','s','w')]
            if not factory:order.append(next(path for path in images if path.endswith('-outside.png')))
            for col,path in enumerate(order):
                with Image.open(path) as source:
                    # Keep the complete frame: clipped geometry remains apparent.
                    source=source.convert('RGB');source.thumbnail((cell_width,row_height-64))
                    sheet.paste(source,(col*cell_width,y+31))
                draw.text((col*cell_width+8,y+row_height-30),('E','N','S','W','Closed exterior')[col],font=font,fill=(190,200,210))
        sheet.save(target,quality=96)
        pages.append(page)
    (out/'index.json').write_text(json.dumps(pages,indent=2))
    print(f'{len(rows)} variants, {len(pages)} pages: {out}')


if __name__=='__main__':main()
