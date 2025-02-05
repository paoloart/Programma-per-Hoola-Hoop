import tkinter as tk
from tkinter import simpledialog, messagebox
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import random
from scipy.optimize import curve_fit
import os
from math import log

# Parametri sperimentali
MIN_DIAM = 17
MAX_DIAM = 50
step_init = 8
min_step = 1
max_inversions = 8
max_trials = 80
target_inversions = 4

# Variabili globali
subject_name = None
trial = 0
last_diam = None
results = []
staircases = [
    {'current_diameter': MIN_DIAM, 'last_response': None, 'step': step_init, 'inversion_count': 0, 'direction': 'up'},
    {'current_diameter': MAX_DIAM, 'last_response': None, 'step': step_init, 'inversion_count': 0, 'direction': 'down'}
]

# Crea le cartelle se non esistono
os.makedirs("pazienti", exist_ok=True)
os.makedirs("immagini", exist_ok=True)

# Funzione logistica per il fitting psicometrico
def logistic(x, alpha, beta):
    return 1.0 / (1.0 + np.exp(-beta * (x - alpha)))

# Funzione per inizializzare il soggetto
def setup_subject():
    global subject_name
    subject_name = simpledialog.askstring("Nome Soggetto", "Inserisci il nome del soggetto (senza spazi):")
    if not subject_name:
        messagebox.showerror("Errore", "Nome non valido: esco.")
        root.quit()

# Funzione per il trial successivo
def next_trial():
    global trial, last_diam
    trial += 1
    current_sc = (trial - 1) % 2
    sc = staircases[current_sc]
    base_diam = sc['current_diameter']

    # Applica dither 1 volta su 3 (-1, 0, +1)
    dither = random.choice([-1, 0, 1]) if random.random() < 0.33 else 0
    new_diam = max(MIN_DIAM, min(base_diam + dither, MAX_DIAM))

    # Evita di ripetere lo stesso diametro consecutivamente
    if last_diam is not None and new_diam == last_diam:
        new_diam = max(MIN_DIAM, min(new_diam + random.choice([-1, 1]), MAX_DIAM))

    last_diam = new_diam
    label_diameter.config(text=f"Trial {trial} - Staircase {current_sc+1}\nDiametro presentato: {new_diam} cm", fg="navy")

# Funzione per registrare la risposta
def record_response(resp):
    global results
    current_sc = (trial - 1) % 2
    sc = staircases[current_sc]

    # Registra la risposta
    results.append({
        "Nome": subject_name,
        "Trial": trial,
        "Staircase": current_sc + 1,
        "Diametro": last_diam,
        "Risposta": resp
    })

    # Controllo inversioni
    if sc['last_response'] is not None and sc['last_response'] != resp:
        sc['inversion_count'] += 1
        if sc['inversion_count'] >= target_inversions:
            sc['step'] = max(min_step, sc['step'] // 2)

    sc['last_response'] = resp

    # Modifica il diametro della staircase
    sc['current_diameter'] += sc['step'] if resp == 0 else -sc['step']
    sc['current_diameter'] = max(MIN_DIAM, min(sc['current_diameter'], MAX_DIAM))

    # Controllo fine esperimento
    if trial >= max_trials or all(sc['inversion_count'] >= max_inversions for sc in staircases):
        finish_experiment()
    else:
        next_trial()

# Funzione per chiudere l'esperimento
def finish_experiment():
    btn_grande.config(state="disabled")
    btn_piccolo.config(state="disabled")
    save_data()
    messagebox.showinfo("Fine esperimento", f"Esperimento completato!\nTrial totali: {trial}")
    root.destroy()
    plot_results()

def save_data():
    df = pd.DataFrame(results)
    filename = f"pazienti/{subject_name}.xlsx"

    # Calcola proporzioni delle risposte per ogni diametro
    grouped = df.groupby('Diametro')['Risposta'].mean().reset_index()
    grouped.columns = ['Diametro', 'Proporzione']

    # Controlla se ci sono meno di 3 valori unici di proporzione (troppi pochi dati intermedi)
    unique_proportions = grouped['Proporzione'].nunique()

    if unique_proportions < 3:
        print("⚠️ Troppi pochi valori intermedi, aggiungo punti fittizi per stabilizzare il fitting.")

        # Trova il valore intermedio
        intermediate_row = grouped[(grouped['Proporzione'] > 0) & (grouped['Proporzione'] < 1)]
        
        if not intermediate_row.empty:
            x_mid = intermediate_row['Diametro'].values[0]
            y_mid = intermediate_row['Proporzione'].values[0]

            # Crea due punti fittizi intorno al valore intermedio
            new_data = pd.DataFrame({
                'Diametro': [x_mid - 1, x_mid + 1],
                'Proporzione': [max(0, y_mid - 0.05), min(1, y_mid + 0.05)]
            })

            # Aggiungi i punti fittizi ai dati originali
            grouped = pd.concat([grouped, new_data]).sort_values(by="Diametro").reset_index(drop=True)

    # Prova il fitting logistico con i nuovi dati
    try:
        popt, pcov = curve_fit(logistic, grouped['Diametro'], grouped['Proporzione'], 
                               p0=[np.median(grouped['Diametro']), 0.5], maxfev=1000)
        alpha, beta = popt
        error_alpha = np.sqrt(np.diag(pcov))[0]
        conf_int_lower = alpha - 1.96 * error_alpha
        conf_int_upper = alpha + 1.96 * error_alpha
    except Exception as e:
        print(f"❌ Errore nel calcolo della soglia: {e}")
        alpha = error_alpha = conf_int_lower = conf_int_upper = np.nan

    # Salva i dati nel file Excel
    with pd.ExcelWriter(filename) as writer:
        df.to_excel(writer, sheet_name="Dati Sperimentali", index=False)

        # Salva i parametri della soglia in un secondo foglio
        threshold_df = pd.DataFrame({
            "Parametro": ["Soglia_50%", "Errore", "Intervallo 95% Inferiore", "Intervallo 95% Superiore"],
            "Valore": [alpha, error_alpha, conf_int_lower, conf_int_upper]
        })
        threshold_df.to_excel(writer, sheet_name="Soglia", index=False)

    print(f"📂 Dati salvati in {filename}")
    save_aggregate_data(df, alpha, error_alpha, conf_int_lower, conf_int_upper)

# Modificare la funzione save_aggregate_data():
def save_aggregate_data(df, alpha, error_alpha, conf_low, conf_high):
    filename = "all_results.xlsx"
    
    # Prepara i dati
    data = {
        "Nome": subject_name,
        "Soglia_50%": alpha,
        "Errore": error_alpha,
        "Intervallo 95% Inferiore": conf_low,
        "Intervallo 95% Superiore": conf_high
    }
    
    # Aggiungi le risposte per diametro
    for d in sorted(df['Diametro'].unique()):
        data[f"Diametro_{d}cm"] = str(df[df['Diametro'] == d]['Risposta'].tolist())

    # Crea o aggiorna il file
    if os.path.exists(filename):
        master_df = pd.read_excel(filename)
        master_df = pd.concat([master_df, pd.DataFrame([data])], ignore_index=True)
    else:
        master_df = pd.DataFrame([data])

    # Riordina le colonne
    cols = ["Nome", "Soglia_50%", "Errore", "Intervallo 95% Inferiore", "Intervallo 95% Superiore"] + \
           [c for c in master_df.columns if c.startswith("Diametro_")]
           
    master_df[cols].to_excel(filename, index=False)
    print(f"📂 Dati aggregati salvati in {filename}")
    
# Funzione per generare il grafico
def plot_results():
    df = pd.DataFrame(results)
    grouped = df.groupby('Diametro')['Risposta'].agg(['mean', 'count']).reset_index()
    grouped.columns = ['Diametro', 'Proporzione', 'Conteggio']

    plt.figure(figsize=(10, 6))
    
    # Plot dati sperimentali
    plt.scatter(grouped['Diametro'], grouped['Proporzione'], 
                s=grouped['Conteggio']*20, alpha=0.6, label='Dati sperimentali')
    
    try:
        # Fitting della curva
        x_data = np.array(grouped['Diametro'])
        y_data = np.array(grouped['Proporzione'])
        
        popt, pcov = curve_fit(logistic, x_data, y_data, p0=[np.median(x_data), 0.5], maxfev=1000)
        alpha, beta = popt
        
        # Creazione curva smooth
        x_fit = np.linspace(MIN_DIAM, MAX_DIAM, 100)
        y_fit = logistic(x_fit, alpha, beta)
        
        plt.plot(x_fit, y_fit, 'r-', label=f'Curva logistica\nα={alpha:.1f} cm\nβ={beta:.2f}')
        plt.legend()
    except Exception as e:
        print(f"Errore nel fitting della curva: {e}")

    plt.title(f"Curva psicometrica - {subject_name}")
    plt.xlabel("Diametro (cm)")
    plt.ylabel("Probabilità risposta 'Troppo grande'")
    plt.grid(True)
    plt.ylim(-0.1, 1.1)
    
    plt.savefig(f"immagini/{subject_name}_psychometric.png")
    plt.show()

# Creazione GUI
root = tk.Tk()
root.title("Esperimento Psicofisico Adattivo")

# Elementi della GUI
label_diameter = tk.Label(root, text="Preparazione...", font=("Arial", 16), pady=20)
label_diameter.pack()

btn_frame = tk.Frame(root)
btn_frame.pack(pady=20)

btn_grande = tk.Button(btn_frame, text="TROPPO GRANDE", 
                      command=lambda: record_response(1),
                      width=15, height=2, bg="tomato", font=("Arial", 12))
btn_piccolo = tk.Button(btn_frame, text="TROPPO PICCOLO", 
                       command=lambda: record_response(0),
                       width=15, height=2, bg="lightgreen", font=("Arial", 12))

btn_grande.pack(side="left", padx=20)
btn_piccolo.pack(side="right", padx=20)

# Inizio esperimento
setup_subject()
next_trial()

root.mainloop()