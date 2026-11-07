"""Read-only dry-run of a controlled local/Hermes comparison. Never sends content."""
import argparse
import json
from pathlib import Path

from app.editorial_critic import critique_plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True,help='Local JSON containing context and local_plan')
    parser.add_argument('--output',type=Path,help='Optional new local report; default stdout')
    args=parser.parse_args()
    payload=json.loads(args.input.read_text(encoding='utf-8'))
    result=critique_plan(payload['context'],payload['local_plan'],capability=payload.get('capability'),dry_run=True)
    report={k:v for k,v in result.items() if k not in {'baseline','critique'}}
    report.update(experiment='same-source-same-plan-local-versus-advisory',review_status='NOT_EVALUATED',
                  policy='dry-run requested by owner; no task executor, model, provider, vision, timeout or cost verified')
    text=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        with args.output.open('x',encoding='utf-8') as handle:handle.write(text)
    else:
        print(text,end='')


if __name__=='__main__':main()
