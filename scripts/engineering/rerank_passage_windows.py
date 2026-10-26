"""Diagnostic scoring windows, not a published chunking/index contract."""
from hashlib import sha256
from langchain_text_splitters import RecursiveCharacterTextSplitter


def paired_windows(candidates, *, size=1200):
    if type(size) is not int or size<100:
        raise ValueError('diagnostic_window_size_invalid')
    splitter=RecursiveCharacterTextSplitter(chunk_size=size,chunk_overlap=0,
        separators=['\n\n','\n','. ','。','; ',' ',''],keep_separator=True,
        strip_whitespace=False)
    output=[];manifest=[]
    for row in candidates:
        body=row['content']
        if sha256(body.encode()).hexdigest()!=row['content_sha256']:
            raise ValueError('diagnostic_original_digest_mismatch')
        parts=splitter.split_text(body)
        if ''.join(parts)!=body:
            raise ValueError('diagnostic_windows_not_lossless')
        output.append(dict(row))
        manifest.append({'node_id':row['node_id'],'parent_id':row['node_id'],
                         'start':0,'end':len(body),'whole':True,'sha256':row['content_sha256']})
        if len(parts)==1:continue
        start=0
        for part in parts:
            end=start+len(part)
            if body[start:end]!=part or len(part)>size:
                raise ValueError('diagnostic_window_offset_mismatch')
            node=row['node_id']+f':diagnostic-window:{start}:{end}'
            digest=sha256(part.encode()).hexdigest()
            # Deliberately construct a scoring view, not an original corpus row
            # with a misleading original embedding identity.
            output.append({'node_id':node,'content':part,'content_sha256':digest,
                           'embedding_context':row.get('embedding_context','')})
            manifest.append({'node_id':node,'parent_id':row['node_id'],'start':start,
                             'end':end,'whole':False,'sha256':digest})
            start=end
    return output,manifest
