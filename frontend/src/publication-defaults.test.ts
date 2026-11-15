import {it,expect} from 'vitest'
import {publicationDefaults} from './publication-defaults'
it('prefers candidate title and saved provider caption',()=>{
  expect(publicationDefaults({name:'Fonte',who:'Canal'},{title:'Título do corte',tx:'Fala original.',captions:{instagram:{text:'Legenda editorial.',origin:'hermes'}}},'instagram',100,2200))
    .toEqual({title:'Título do corte',caption:'Legenda editorial.'})
})
it('uses literal speech and creator credit without inventing text',()=>{
  expect(publicationDefaults({name:'Título da fonte',who:'Canal'},{title:'',tx:'Uma frase completa. Outra frase.',captions:null},'instagram',100,2200))
    .toEqual({title:'Título da fonte',caption:'Uma frase completa.\n\nFonte: Canal'})
})
it('respects the selected provider limits',()=>{
  const d=publicationDefaults({name:'abcdefghij',who:'Canal'},{tx:'Uma frase completa.',captions:null},'youtube',5,10)
  expect(d.title).toBe('abcde');expect(Array.from(d.caption).length).toBe(10)
})
