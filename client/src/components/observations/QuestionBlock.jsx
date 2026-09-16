import React from 'react';
import { MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';

export const QuestionBlock = ({ question, field, students, onToggleStudent, selections }) => {
  const { toast } = useToast();
  const handleComment = () => {
    toast({
      title: '🚧 Comentário por criança em breve!',
      description: 'Esta funcionalidade ainda não foi implementada.',
    });
  };

  return (
    <div className="bg-white p-4 rounded-2xl shadow-md border border-gray-100 mb-4">
      <p className="text-sm font-semibold text-[#8A63D2] mb-1">{field}</p>
      <p className="font-semibold text-gray-700 mb-4">{question.question}</p>
      <div className="space-y-3">
        {students.map(student => (
          <div key={student.id} className="flex items-center justify-between">
            <div className="flex items-center">
              <Checkbox
                id={`${question.id}-${student.id}`}
                checked={selections.includes(student.id)}
                onCheckedChange={() => onToggleStudent(student.id)}
                className="h-5 w-5"
              />
              <Label htmlFor={`${question.id}-${student.id}`} className="ml-3 text-gray-600">{student.name}</Label>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleComment}>
              <MessageSquare className="h-4 w-4 text-gray-400" />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
};