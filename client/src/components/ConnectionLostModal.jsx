import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { WifiOff, RefreshCw } from 'lucide-react';

export function ConnectionLostModal({ open, checking, onRetry }) {
  return (
    <Dialog open={open}>
      <DialogContent
        className="sm:max-w-md [&>button:last-child]:hidden"
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader className="items-center text-center">
          <div className="bg-red-100 p-3 rounded-full mx-auto mb-2">
            <WifiOff className="h-6 w-6 text-red-600" />
          </div>
          <DialogTitle>Conexão perdida</DialogTitle>
          <DialogDescription>
            Não foi possível conectar ao servidor. Verifique sua internet e tente novamente.
          </DialogDescription>
        </DialogHeader>
        <div className="flex justify-center mt-2">
          <Button onClick={onRetry} disabled={checking}>
            <RefreshCw className={`h-4 w-4 mr-2 ${checking ? 'animate-spin' : ''}`} />
            {checking ? 'Verificando...' : 'Tentar reconexão'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
