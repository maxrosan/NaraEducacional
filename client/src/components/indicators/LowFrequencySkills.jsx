import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';

const SkillStatus = ({ count }) => {
    if (count === 0) return <span className="text-xl">🔴</span>;
    if (count <= 2) return <span className="text-xl">🟡</span>;
    return <span className="text-xl">✅</span>;
};

const LowFrequencySkills = ({ data, skills }) => {
    
    const getSkillStatus = (studentSkills, skillId) => {
        const skill = studentSkills.find(s => s.id === skillId);
        return skill ? skill.count : 0;
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">Habilidades com Baixa Frequência de Registros</CardTitle>
                <CardDescription>Acompanhe a cobertura das habilidades da BNCC por criança.</CardDescription>
            </CardHeader>
            <CardContent>
                <Accordion type="single" collapsible className="w-full">
                    {data.map(student => (
                        <AccordionItem value={`item-${student.id}`} key={student.id}>
                            <AccordionTrigger className="font-bold text-base">{student.name}</AccordionTrigger>
                            <AccordionContent>
                                <ul className="space-y-3 pl-2">
                                    {skills.map(skill => {
                                        const count = getSkillStatus(student.skills, skill.id);
                                        return (
                                            <li key={skill.id} className="flex items-start gap-3">
                                                <div className="pt-1">
                                                   <SkillStatus count={count} />
                                                </div>
                                                <p className="text-sm text-gray-700">
                                                    {skill.description} 
                                                    <span className="font-bold text-gray-500 text-xs ml-2">({count} {count === 1 ? 'registro' : 'registros'})</span>
                                                </p>
                                            </li>
                                        );
                                    })}
                                </ul>
                            </AccordionContent>
                        </AccordionItem>
                    ))}
                </Accordion>
            </CardContent>
        </Card>
    );
};

export default LowFrequencySkills;