import React from 'react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { safeFormatDate } from '@/lib/dateUtils';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Pencil, Trash2 } from 'lucide-react';

const PortfolioItemCard = ({ item, onSelect, onEdit, onDelete }) => {
  return (
    <Card className="flex flex-col overflow-hidden transition-shadow hover:shadow-lg">
      <div className="relative">
        <img
          src={item.media_urls?.[0] || item.arquivo_url}
          alt={item.descricao || 'Registro do portfólio'}
          className="w-full h-auto object-contain"
        />
        <div className="absolute top-2 left-2">
          <Checkbox
            checked={item.para_relatorio}
            onCheckedChange={(checked) => onSelect(item.id, checked)}
            className="bg-white"
          />
        </div>
      </div>
      <CardContent className="p-4 flex-grow">
        <div className="flex justify-between items-start mb-2">
          <p className="text-xs text-gray-500">{safeFormatDate(item.data_registro, 'dd/MM/yyyy', { locale: ptBR })}</p>
          {item.projeto && <Badge variant="secondary">{item.projeto}</Badge>}
        </div>
        <p className="text-sm text-gray-700 mb-2 min-h-[40px]">{item.descricao || 'Sem legenda'}</p>
      </CardContent>
      <CardFooter className="p-2 bg-gray-50 flex justify-end gap-1">
        <Button variant="ghost" size="icon" onClick={() => onEdit(item)} className="h-8 w-8">
          <Pencil className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={() => onDelete(item.producao_id || item.id)} className="text-red-500 h-8 w-8">
          <Trash2 className="h-4 w-4" />
        </Button>
      </CardFooter>
    </Card>
  );
};

export default PortfolioItemCard;
