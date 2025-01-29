import os
import tkinter as tk
from tkinter import simpledialog, messagebox
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import math

from scipy.optimize import curve_fit

def logistic(x, alpha, beta):
    """
    Curva logistica:
      alpha = soglia (punto al 50%)
      beta  = pendenza
    """
    return 1.0 / (1.0 + np.exp(-beta * (x - alpha)))

class TwoStaircasesApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Esperimento Hoola Hoop")
        
        # Cartelle necessarie
        os.makedirs("pazienti", exist_ok=True)
        os.makedirs("immagini", exist_ok=True)
        
        # Carichiamo (o creiamo) il database Excel globale in pazienti/database_globale.xlsx
        self.global_db_path = "pazienti/database_globale.xlsx"
        self.df_global = self.load_or_create_global_db(self.global_db_path)
        
        # Range dei diametri
        self.MIN_DIAM = 17
        self.MAX_DIAM = 50
        
        # Staircase ascendente
        self.current_diam_up = 17   # parte dal minimo
        self.step_up = 5
        self.min_step_up = 1
        self.last_resp_up = None
        self.inversion_up = 0
        
        # Staircase discendente
        self.current_diam_down = 50 # parte dal massimo
        self.step_down = 5
        self.min_step_down = 1
        self.last_resp_down = None
        self.inversion_down = 0
        
        # Numero di prove e criteri di stop
        self.trial = 0
        self.max_trials = 50   # max 50 prove
        self.min_trials = 20   # almeno 20 prove
        self.max_inversions = 15  # somma di up+down => stop
        
        # Risultati (long format)
        self.results = []
        
        # Chiediamo il nome del soggetto
        self.subject_name = simpledialog.askstring(
            "Nome Soggetto",
            "Inserisci il nome del soggetto (senza spazi):"
        )
        if not self.subject_name:
            messagebox.showerror("Errore", "Nome non valido: esco.")
            master.quit()
        
        # Etichetta che mostra il diametro da presentare
        self.label_diameter = tk.Label(
            master,
            text=f"Diametro da presentare: {self.current_diam_up} cm",
            font=("Arial", 16)
        )
        self.label_diameter.pack(pady=20)
        
        # Bottoni di risposta
        self.btn_grande = tk.Button(
            master, text="Troppo grande",
            command=lambda: self.record_response(1),
            width=15, height=2, bg="tomato"
        )
        self.btn_piccolo = tk.Button(
            master, text="Troppo piccolo",
            command=lambda: self.record_response(0),
            width=15, height=2, bg="lightgreen"
        )
        
        self.btn_grande.pack(side="left", padx=20, pady=20)
        self.btn_piccolo.pack(side="right", padx=20, pady=20)
        
        # Livelli di probabilità p per cui calcolare i diametri corrispondenti
        self.p_levels = [0.5, 0.7, 0.8]
    
    def load_or_create_global_db(self, path):
        """
        Se esiste 'pazienti/database_globale.xlsx', lo carica.
        Altrimenti lo crea con colonne: Nome, 10, 11, ... 50
        """
        if os.path.exists(path):
            df_global = pd.read_excel(path, engine='openpyxl')
            print("Database globale caricato da:", path)
        else:
            cols = ["Nome"] + [str(d) for d in range(10, 51)]
            df_global = pd.DataFrame(columns=cols)
            df_global.to_excel(path, index=False, engine='openpyxl')
            print("Creato nuovo database globale in:", path)
        return df_global
    
    def record_response(self, resp):
        """Registra la risposta, aggiorna la staircase corrispondente, gestisce lo stop."""
        self.trial += 1
        
        # Alterniamo: trial dispari -> ascendente, pari -> discendente
        if self.trial % 2 == 1:
            # Staircase ascendente
            staircase_name = "Ascendente"
            diam = self.current_diam_up
            
            # Salvataggio riga
            self.results.append({
                "Nome": self.subject_name,
                "Trial": self.trial,
                "Staircase": staircase_name,
                "Diametro": diam,
                "Risposta": resp
            })
            
            # Check inversione
            if self.last_resp_up is not None and self.last_resp_up != resp:
                self.inversion_up += 1
                if self.step_up > self.min_step_up:
                    self.step_up -= 1
            
            self.last_resp_up = resp
            
            # Aggiorna diametro
            if resp == 1:
                new_diam = diam - self.step_up
            else:
                new_diam = diam + self.step_up
            
            if new_diam < self.MIN_DIAM:
                new_diam = self.MIN_DIAM
            elif new_diam > self.MAX_DIAM:
                new_diam = self.MAX_DIAM
            self.current_diam_up = new_diam
        
        else:
            # Staircase discendente
            staircase_name = "Discendente"
            diam = self.current_diam_down
            
            self.results.append({
                "Nome": self.subject_name,
                "Trial": self.trial,
                "Staircase": staircase_name,
                "Diametro": diam,
                "Risposta": resp
            })
            
            if self.last_resp_down is not None and self.last_resp_down != resp:
                self.inversion_down += 1
                if self.step_down > self.min_step_down:
                    self.step_down -= 1
            
            self.last_resp_down = resp
            
            # Aggiorna diametro
            if resp == 1:
                new_diam = diam - self.step_down
            else:
                new_diam = diam + self.step_down
            
            if new_diam < self.MIN_DIAM:
                new_diam = self.MIN_DIAM
            elif new_diam > self.MAX_DIAM:
                new_diam = self.MAX_DIAM
            self.current_diam_down = new_diam
        
        # Somma inversioni
        total_inversions = self.inversion_up + self.inversion_down
        
        # Criteri di stop
        if ((total_inversions >= self.max_inversions and self.trial >= self.min_trials)
            or (self.trial >= self.max_trials)):
            self.finish_experiment()
        else:
            # Prossimo trial
            if (self.trial + 1) % 2 == 1:
                next_diam = self.current_diam_up
                next_stair = "StairUp"
            else:
                next_diam = self.current_diam_down
                next_stair = "StairDown"
            
            self.label_diameter.config(
                text=f"Diametro da presentare: {next_diam} cm ({next_stair})"
            )
    
    def finish_experiment(self):
        """Salva i dati, chiude GUI, fa il fit+plot, aggiorna Excel globale."""
        self.btn_grande.config(state="disabled")
        self.btn_piccolo.config(state="disabled")
        
        # DataFrame con i risultati "lunghi" del paziente
        df = pd.DataFrame(self.results)
        
        # Salva i dati del singolo paziente in CSV
        single_csv = f"pazienti/{self.subject_name}.csv"
        df.to_csv(single_csv, index=False)
        
        total_inversions = self.inversion_up + self.inversion_down
        msg = (f"Esperimento terminato!\n"
               f"Prove totali: {self.trial}\n"
               f"Inversioni totali: {total_inversions}\n"
               f"Dati salvati in {single_csv}.")
        messagebox.showinfo("Fine esperimento", msg)
        
        self.master.destroy()
        
        # Plot + fit
        self.plot_and_fit(df)
        
        # Aggiorniamo l'excel globale
        self.update_global_db_excel(df)
    
    def plot_and_fit(self, df):
        grouped = df.groupby("Diametro")["Risposta"]
        prop = grouped.mean().reset_index(name="Prop1")  # proporzione di '1'
        prop.sort_values(by="Diametro", inplace=True)
        
        x_data = prop["Diametro"].values
        y_data = prop["Prop1"].values
        
        if len(x_data) < 3:
            self.plot_empirical_only(x_data, y_data)
            return
        
        alpha_guess = np.median(x_data)
        beta_guess = 1.0
        
        try:
            popt, pcov = curve_fit(logistic, x_data, y_data, p0=[alpha_guess, beta_guess])
            alpha_fit, beta_fit = popt
            
            x_fit = np.linspace(self.MIN_DIAM, self.MAX_DIAM, 200)
            y_fit = logistic(x_fit, alpha_fit, beta_fit)
            
            plt.figure(figsize=(8,5))
            plt.scatter(x_data, y_data, color="blue", label="Dati empirici")
            plt.plot(x_fit, y_fit, 'r-', label="Curva logistica fittata")
            plt.ylim(0,1)
            plt.xlim(self.MIN_DIAM, self.MAX_DIAM)
            plt.axhline(0.5, color='gray', linestyle='--')
            plt.title(f"Curva psicometrica - {self.subject_name}")
            plt.xlabel("Diametro (cm)")
            plt.ylabel("Proporzione 'Troppo grande'")
            plt.legend()
            plt.grid(True)
            
            png_name = f"{self.subject_name}.png"
            plt.savefig(f"immagini/{png_name}", dpi=300)
            plt.show()
            
            soglie_messaggio = []
            for p_target in self.p_levels:
                ratio = p_target/(1-p_target)
                x_val = alpha_fit + (1.0/beta_fit)*math.log(ratio)
                soglie_messaggio.append(f"p={int(p_target*100)}% => {x_val:.2f} cm")
            
            soglie_txt = "\n".join(soglie_messaggio)
            msg_fit = (
                f"Soglia al 50% (alpha): ~{alpha_fit:.2f} cm\n"
                f"Pendenza (beta): ~{beta_fit:.2f}\n\n"
                f"Altre soglie richieste:\n{soglie_txt}\n\n"
                f"Plot salvato in immagini/{png_name} (300dpi)"
            )
            print(msg_fit)
            messagebox.showinfo("Risultati Fitting", msg_fit)
            
        except Exception as e:
            print("Errore nel fitting:", e)
            self.plot_empirical_only(x_data, y_data)
    
    def plot_empirical_only(self, x_data, y_data):
        plt.figure(figsize=(8,5))
        plt.scatter(x_data, y_data, color="blue", label="Dati empirici")
        plt.ylim(0,1)
        plt.xlim(self.MIN_DIAM, self.MAX_DIAM)
        plt.axhline(0.5, color='gray', linestyle='--')
        plt.title(f"Curva empirica - {self.subject_name}")
        plt.xlabel("Diametro (cm)")
        plt.ylabel("Proporzione 'Troppo grande'")
        plt.grid(True)
        plt.legend()
        plt.show()
    
    def update_global_db_excel(self, df):
        """
        Aggiorna la tabella Excel 'pazienti/database_globale.xlsx' (df_global)
        con i dati di self.subject_name: una riga, col Nome e col diametro [10..50].
        """
        # Calcoliamo la prop di "TroppoGrande" (1) per diametri 10..50
        grouped = df.groupby("Diametro")["Risposta"]
        p_grande = grouped.mean()  # diam->prop(1)
        
        # Prepariamo un dict per la riga
        row_data = {"Nome": self.subject_name}
        for diam in range(10,51):
            col = str(diam)
            row_data[col] = p_grande[diam] if diam in p_grande.index else 0.0
        
        # Cerchiamo se esiste già la riga col nome paziente
        existing_idx = self.df_global.index[self.df_global["Nome"] == self.subject_name].tolist()
        
        if existing_idx:
            # Aggiorniamo
            idx = existing_idx[0]
            for diam in range(10,51):
                c = str(diam)
                self.df_global.at[idx, c] = row_data[c]
        else:
            # Aggiungiamo riga
            self.df_global = self.df_global.append(row_data, ignore_index=True)
        
        # Salviamo sullo stesso file Excel
        self.df_global.to_excel(self.global_db_path, index=False, engine='openpyxl')
        print(f"Aggiornato Excel globale: {self.global_db_path}")

def main():
    root = tk.Tk()
    app = TwoStaircasesApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
