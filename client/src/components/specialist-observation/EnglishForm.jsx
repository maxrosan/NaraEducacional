import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';

const EnglishForm = ({ turmaNivel }) => {
  return (
    <Card className="w-full border-0 shadow-none">
      <CardHeader>
        <CardTitle className="text-lg">Observação de Inglês</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label className="font-semibold">Participação e Engajamento</Label>
          <RadioGroup defaultValue="active">
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="active" id="eng-active" />
              <Label htmlFor="eng-active">Ativo e entusiasmado</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="passive" id="eng-passive" />
              <Label htmlFor="eng-passive">Observador, mas atento</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="reluctant" id="eng-reluctant" />
              <Label htmlFor="eng-reluctant">Relutante em participar</Label>
            </div>
          </RadioGroup>
        </div>

        <div className="space-y-2">
          <Label htmlFor="comprehension" className="font-semibold">Compreensão Oral</Label>
          <Textarea id="comprehension" placeholder="Ex: Compreende comandos simples como 'sit down', 'stand up' e nomes de cores." />
        </div>
        
        <div className="space-y-2">
          <Label htmlFor="expression" className="font-semibold">Expressão Oral</Label>
          <Textarea id="expression" placeholder="Ex: Repete palavras e pequenas frases. Arrisca nomes de animais e objetos em inglês." />
        </div>

        <div className="space-y-2">
          <Label htmlFor="notes" className="font-semibold">Observações Adicionais</Label>
          <Textarea id="notes" placeholder="Descreva outras percepções relevantes sobre a interação da criança com a língua inglesa." />
        </div>
      </CardContent>
    </Card>
  );
};

export default EnglishForm;