import React, { useState, useMemo } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  // Ícones pedagógicos e educacionais
  Users, MessageCircle, Shapes, Palette, Music, Book, BookOpen,
  Pencil, PenTool, Brush, Image, Camera, Video, Mic,
  Brain, Lightbulb, Puzzle, Target, Award, Star, Heart,
  // Ícones de movimento e corpo
  Footprints, Hand, Eye, Ear, Smile, Baby,
  // Ícones de natureza e ciências
  Leaf, TreeDeciduous, Flower2, Sun, Moon, Cloud, Droplets,
  Bug, Bird, Fish, Cat, Dog,
  // Ícones de números e lógica
  Calculator, Hash, Percent, BarChart2, PieChart, TrendingUp,
  // Ícones de tempo e espaço
  Clock, Calendar, Map, Compass, Globe, Home, Building,
  // Ícones de objetos e ferramentas
  Scissors, Ruler, Wrench, Settings, Gamepad2, Dices,
  // Ícones de comunicação
  MessageSquare, Mail, Phone, Share2, Link,
  // Ícones gerais
  Sparkles, Zap, Flame, Crown, Diamond, Gift, PartyPopper,
  Rocket, Plane, Car, Bike, Ship,
  Apple, Coffee, Utensils, Cookie,
  // Ícones da biblioteca ToyBrick que já usamos
  ToyBrick
} from 'lucide-react';

// Biblioteca de ícones disponíveis para seleção, organizados por categoria
export const iconLibrary = {
  // Ícones pedagógicos
  'Users': { icon: Users, label: 'Pessoas', category: 'Pessoas' },
  'MessageCircle': { icon: MessageCircle, label: 'Comunicação', category: 'Comunicação' },
  'Shapes': { icon: Shapes, label: 'Formas', category: 'Formas' },
  'Palette': { icon: Palette, label: 'Arte', category: 'Arte' },
  'ToyBrick': { icon: ToyBrick, label: 'Brinquedo', category: 'Brinquedos' },
  'Music': { icon: Music, label: 'Música', category: 'Arte' },
  'Book': { icon: Book, label: 'Livro', category: 'Educação' },
  'BookOpen': { icon: BookOpen, label: 'Livro Aberto', category: 'Educação' },
  'Pencil': { icon: Pencil, label: 'Lápis', category: 'Escrita' },
  'PenTool': { icon: PenTool, label: 'Caneta', category: 'Escrita' },
  'Brush': { icon: Brush, label: 'Pincel', category: 'Arte' },
  'Image': { icon: Image, label: 'Imagem', category: 'Arte' },
  'Camera': { icon: Camera, label: 'Câmera', category: 'Mídia' },
  'Video': { icon: Video, label: 'Vídeo', category: 'Mídia' },
  'Mic': { icon: Mic, label: 'Microfone', category: 'Mídia' },
  'Brain': { icon: Brain, label: 'Cérebro', category: 'Cognição' },
  'Lightbulb': { icon: Lightbulb, label: 'Ideia', category: 'Cognição' },
  'Puzzle': { icon: Puzzle, label: 'Quebra-cabeça', category: 'Jogos' },
  'Target': { icon: Target, label: 'Alvo', category: 'Objetivos' },
  'Award': { icon: Award, label: 'Prêmio', category: 'Conquistas' },
  'Star': { icon: Star, label: 'Estrela', category: 'Conquistas' },
  'Heart': { icon: Heart, label: 'Coração', category: 'Emoções' },

  // Corpo e movimento
  'Footprints': { icon: Footprints, label: 'Passos', category: 'Movimento' },
  'Hand': { icon: Hand, label: 'Mão', category: 'Corpo' },
  'Eye': { icon: Eye, label: 'Olho', category: 'Sentidos' },
  'Ear': { icon: Ear, label: 'Ouvido', category: 'Sentidos' },
  'Smile': { icon: Smile, label: 'Sorriso', category: 'Emoções' },
  'Baby': { icon: Baby, label: 'Bebê', category: 'Pessoas' },

  // Natureza
  'Leaf': { icon: Leaf, label: 'Folha', category: 'Natureza' },
  'TreeDeciduous': { icon: TreeDeciduous, label: 'Árvore', category: 'Natureza' },
  'Flower2': { icon: Flower2, label: 'Flor', category: 'Natureza' },
  'Sun': { icon: Sun, label: 'Sol', category: 'Natureza' },
  'Moon': { icon: Moon, label: 'Lua', category: 'Natureza' },
  'Cloud': { icon: Cloud, label: 'Nuvem', category: 'Natureza' },
  'Droplets': { icon: Droplets, label: 'Gotas', category: 'Natureza' },
  'Bug': { icon: Bug, label: 'Inseto', category: 'Animais' },
  'Bird': { icon: Bird, label: 'Pássaro', category: 'Animais' },
  'Fish': { icon: Fish, label: 'Peixe', category: 'Animais' },
  'Cat': { icon: Cat, label: 'Gato', category: 'Animais' },
  'Dog': { icon: Dog, label: 'Cachorro', category: 'Animais' },

  // Números e lógica
  'Calculator': { icon: Calculator, label: 'Calculadora', category: 'Matemática' },
  'Hash': { icon: Hash, label: 'Números', category: 'Matemática' },
  'Percent': { icon: Percent, label: 'Porcentagem', category: 'Matemática' },
  'BarChart2': { icon: BarChart2, label: 'Gráfico', category: 'Matemática' },
  'PieChart': { icon: PieChart, label: 'Pizza', category: 'Matemática' },
  'TrendingUp': { icon: TrendingUp, label: 'Tendência', category: 'Matemática' },

  // Tempo e espaço
  'Clock': { icon: Clock, label: 'Relógio', category: 'Tempo' },
  'Calendar': { icon: Calendar, label: 'Calendário', category: 'Tempo' },
  'Map': { icon: Map, label: 'Mapa', category: 'Espaço' },
  'Compass': { icon: Compass, label: 'Bússola', category: 'Espaço' },
  'Globe': { icon: Globe, label: 'Globo', category: 'Espaço' },
  'Home': { icon: Home, label: 'Casa', category: 'Lugares' },
  'Building': { icon: Building, label: 'Prédio', category: 'Lugares' },

  // Ferramentas
  'Scissors': { icon: Scissors, label: 'Tesoura', category: 'Ferramentas' },
  'Ruler': { icon: Ruler, label: 'Régua', category: 'Ferramentas' },
  'Wrench': { icon: Wrench, label: 'Chave', category: 'Ferramentas' },
  'Settings': { icon: Settings, label: 'Config', category: 'Ferramentas' },
  'Gamepad2': { icon: Gamepad2, label: 'Jogos', category: 'Jogos' },
  'Dices': { icon: Dices, label: 'Dados', category: 'Jogos' },

  // Comunicação
  'MessageSquare': { icon: MessageSquare, label: 'Mensagem', category: 'Comunicação' },
  'Mail': { icon: Mail, label: 'Email', category: 'Comunicação' },
  'Phone': { icon: Phone, label: 'Telefone', category: 'Comunicação' },
  'Share2': { icon: Share2, label: 'Compartilhar', category: 'Comunicação' },
  'Link': { icon: Link, label: 'Link', category: 'Comunicação' },

  // Especiais
  'Sparkles': { icon: Sparkles, label: 'Brilhos', category: 'Especiais' },
  'Zap': { icon: Zap, label: 'Raio', category: 'Especiais' },
  'Flame': { icon: Flame, label: 'Chama', category: 'Especiais' },
  'Crown': { icon: Crown, label: 'Coroa', category: 'Especiais' },
  'Diamond': { icon: Diamond, label: 'Diamante', category: 'Especiais' },
  'Gift': { icon: Gift, label: 'Presente', category: 'Especiais' },
  'PartyPopper': { icon: PartyPopper, label: 'Festa', category: 'Especiais' },

  // Veículos
  'Rocket': { icon: Rocket, label: 'Foguete', category: 'Veículos' },
  'Plane': { icon: Plane, label: 'Avião', category: 'Veículos' },
  'Car': { icon: Car, label: 'Carro', category: 'Veículos' },
  'Bike': { icon: Bike, label: 'Bicicleta', category: 'Veículos' },
  'Ship': { icon: Ship, label: 'Navio', category: 'Veículos' },

  // Comida
  'Apple': { icon: Apple, label: 'Maçã', category: 'Alimentos' },
  'Coffee': { icon: Coffee, label: 'Café', category: 'Alimentos' },
  'Utensils': { icon: Utensils, label: 'Talheres', category: 'Alimentos' },
  'Cookie': { icon: Cookie, label: 'Biscoito', category: 'Alimentos' },
};

// Helper para obter o componente de ícone pelo nome
export const getIconComponent = (iconName) => {
  return iconLibrary[iconName]?.icon || BookOpen;
};

// Componente de seleção de ícones
const IconPicker = ({ selectedIcon, onSelect, className = '' }) => {
  const [search, setSearch] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  // Agrupar ícones por categoria
  const groupedIcons = useMemo(() => {
    const groups = {};
    Object.entries(iconLibrary).forEach(([key, value]) => {
      const category = value.category || 'Outros';
      if (!groups[category]) groups[category] = [];
      groups[category].push({ key, ...value });
    });
    return groups;
  }, []);

  // Filtrar ícones pela busca
  const filteredGroups = useMemo(() => {
    if (!search) return groupedIcons;

    const searchLower = search.toLowerCase();
    const filtered = {};

    Object.entries(groupedIcons).forEach(([category, icons]) => {
      const matchingIcons = icons.filter(
        icon =>
          icon.label.toLowerCase().includes(searchLower) ||
          icon.key.toLowerCase().includes(searchLower) ||
          category.toLowerCase().includes(searchLower)
      );
      if (matchingIcons.length > 0) {
        filtered[category] = matchingIcons;
      }
    });

    return filtered;
  }, [groupedIcons, search]);

  const SelectedIconComponent = selectedIcon ? getIconComponent(selectedIcon) : null;

  return (
    <div className={`relative ${className}`}>
      <Button
        type="button"
        variant="outline"
        className="w-full justify-start gap-2"
        onClick={() => setIsOpen(!isOpen)}
      >
        {SelectedIconComponent ? (
          <>
            <SelectedIconComponent className="h-5 w-5 text-purple-600" />
            <span>{iconLibrary[selectedIcon]?.label || selectedIcon}</span>
          </>
        ) : (
          <span className="text-muted-foreground">Escolha um ícone...</span>
        )}
      </Button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute z-50 mt-1 w-80 max-h-96 overflow-hidden bg-white border rounded-lg shadow-xl">
            <div className="p-2 border-b sticky top-0 bg-white">
              <Input
                placeholder="Buscar ícone..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8"
                autoFocus
              />
            </div>
            <div className="overflow-y-auto max-h-72 p-2">
              {Object.entries(filteredGroups).map(([category, icons]) => (
                <div key={category} className="mb-3">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                    {category}
                  </p>
                  <div className="grid grid-cols-6 gap-1">
                    {icons.map(({ key, icon: Icon, label }) => (
                      <button
                        key={key}
                        type="button"
                        title={label}
                        className={`p-2 rounded-md hover:bg-purple-100 transition-colors ${
                          selectedIcon === key ? 'bg-purple-200 ring-2 ring-purple-500' : ''
                        }`}
                        onClick={() => {
                          onSelect(key);
                          setIsOpen(false);
                          setSearch('');
                        }}
                      >
                        <Icon className="h-5 w-5 mx-auto text-gray-700" />
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              {Object.keys(filteredGroups).length === 0 && (
                <p className="text-center text-gray-500 py-4">
                  Nenhum ícone encontrado para "{search}"
                </p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default IconPicker;
