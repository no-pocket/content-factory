import {Component} from 'react'
import type {ReactNode} from 'react'
export class ErrorBoundary extends Component<{children:ReactNode},{failed:boolean}>{
  state={failed:false}
  static getDerivedStateFromError(){return {failed:true}}
  render(){return this.state.failed?<main role="alert"><h1>Não foi possível abrir esta tela</h1><p>Recarregue a página para tentar novamente.</p><div className="ac"><button className="b" onClick={()=>location.reload()}>Recarregar</button><button className="b" onClick={()=>{location.hash='painel';location.reload()}}>Voltar ao Painel</button></div></main>:this.props.children}
}
