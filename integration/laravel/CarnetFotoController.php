<?php
// app/Http/Controllers/CarnetFotoController.php
// Ruta: Route::post('/carnet/foto', [CarnetFotoController::class, 'store'])->middleware('auth');

namespace App\Http\Controllers;

use App\Services\PhotoValidatorService;
use Illuminate\Http\Request;

class CarnetFotoController extends Controller
{
    public function store(Request $request, PhotoValidatorService $validador)
    {
        $request->validate(['foto' => 'required|image|mimes:jpeg,png,webp|max:5120']);
        $estudiante = $request->user();                       // ajusta a tu modelo
        $r = $validador->validate($request->file('foto'), $estudiante->codigo);

        // Guarda el resultado en tu sistema (ejemplo)
        $estudiante->update([
            'foto_validacion_id' => $r['validation_id'] ?? null,
            'foto_estado'        => $r['status'],             // APPROVED | REJECTED | MANUAL_REVIEW
        ]);

        return match ($r['status']) {
            'APPROVED'      => back()->with('ok', $r['message']),
            'MANUAL_REVIEW' => back()->with('info', $r['message']),
            default         => back()->withErrors([
                'foto' => 'Tu fotografía ha sido rechazada porque no cumple con los requisitos.',
            ])->with('motivos', $r['rejection_reasons'])->with('recomendaciones', $r['recommendations']),
        };
    }
}

/* En la vista Blade:
@if(session('motivos'))
  <div class="alert alert-danger">
    <b>Motivos:</b><ul>@foreach(session('motivos') as $m)<li>{{ $m }}</li>@endforeach</ul>
    <b>Recomendaciones:</b><ul>@foreach(session('recomendaciones') as $m)<li>{{ $m }}</li>@endforeach</ul>
  </div>
@endif
*/
