declare module 'react-sparklines' {
  import { Component } from 'react';

  interface SparklinesProps {
    data: number[];
    width?: number;
    height?: number;
    color?: string;
    children?: React.ReactNode;
  }

  export default class Sparklines extends Component<SparklinesProps> {}
  
  export class SparklinesLine extends Component<{ style?: React.CSSProperties }> {}
}

