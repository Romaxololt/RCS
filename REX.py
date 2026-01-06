import sys, os, argparse
import time
from colorama import Fore, Style, init

init(autoreset=True)

class DebugLogger:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.indent_level = 0
    
    def log(self, msg, color=Fore.CYAN):
        if self.enabled:
            indent = "  " * self.indent_level
            print(f"{color}{indent}[DEBUG] {msg}{Style.RESET_ALL}")
    
    def error(self, msg):
        if self.enabled:
            indent = "  " * self.indent_level
            print(f"{Fore.RED}{indent}[ERROR] {msg}{Style.RESET_ALL}")
    
    def success(self, msg):
        if self.enabled:
            indent = "  " * self.indent_level
            print(f"{Fore.GREEN}{indent}[SUCCESS] {msg}{Style.RESET_ALL}")
    
    def info(self, msg):
        if self.enabled:
            indent = "  " * self.indent_level
            print(f"{Fore.YELLOW}{indent}[INFO] {msg}{Style.RESET_ALL}")
    
    def indent(self):
        self.indent_level += 1
    
    def dedent(self):
        if self.indent_level > 0:
            self.indent_level -= 1

class CompilerError(Exception):
    def __init__(self, msg, line_num=None):
        self.msg = msg
        self.line_num = line_num
        super().__init__(msg)
    
    def display(self):
        if self.line_num:
            print(f"{Fore.RED}╔═══ Syntax Error at line {self.line_num} ═══╗{Style.RESET_ALL}")
            print(f"{Fore.RED}║ {self.msg:<50} ║{Style.RESET_ALL}")
            print(f"{Fore.RED}╚{'═' * 54}╝{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}╔═══ Syntax Error ═══╗{Style.RESET_ALL}")
            print(f"{Fore.RED}║ {self.msg:<50} ║{Style.RESET_ALL}")
            print(f"{Fore.RED}╚{'═' * 54}╝{Style.RESET_ALL}")

class ProgBar:
    def __init__(self, el, real=False):
        self.el = el
        self.act = 0
        self.last_update = 0
        self.real = real
        
    def increment(self):
        self.act += 1
        
    def show(self, force=False):
        if self.real:
            return
        current_time = time.time()
        if force or (current_time - self.last_update) >= 0.1:
            n_hashtag = int(self.act/self.el*100)
            bar = f"{Fore.GREEN}{'█' * n_hashtag}{Fore.WHITE}{'░' * (100 - n_hashtag)}{Style.RESET_ALL}"
            print(f"[{bar}] {self.act}/{self.el}", end="\r")
            self.last_update = current_time

class REXCompiler:
    def __init__(self, debug_logger):
        self.c_code = [
            "//REX-C Compiler",
            "#include <stdio.h>",
            "#include <stdlib.h>",
            "#include <string.h>"
        ]
        self.variables = {}
        self.labels = {}
        self.functions = {}
        self.constants = {}
        self.logger = debug_logger
        self.current_line = 0
        self.skip_next = False
        self.in_function = False
        self.current_function = None
        self.function_code = []
        self.main_code = []
        
    def add_line(self, code):
        if self.in_function:
            self.function_code.append(code)
        else:
            self.main_code.append(code)
        
    def finalize(self):
        # Assembler le code final
        final_code = self.c_code.copy()
        final_code.extend(self.function_code)
        final_code.append("int main() {")
        final_code.extend(self.main_code)
        final_code.append("return 0;}")
        return "\n".join(final_code)
    
    def _check_var_exists(self, var):
        # CORRECTION: Vérifier aussi dans les constantes
        if var not in self.variables and var not in self.constants:
            raise CompilerError(f"Variable '{var}' not defined", self.current_line)
    
    def check_label_exists(self):
        for k, v in self.labels.items():
            if v == False:
                raise CompilerError(f"Label '{k}' not defined")
        
    def _check_var_type(self, var, expected_type):
        if self.variables[var]["type"] != expected_type:
            raise CompilerError(
                f"Type mismatch: '{var}' is {self.variables[var]['type']}, expected {expected_type}",
                self.current_line
            )
    
    def _get_c_type(self, tip):
        """Convert REX type to C type"""
        type_map = {
            "INT": "int",
            "FLOAT": "float",
            "BOOL": "int",
            "STR": "char*",
            "VOID": "void"
        }
        return type_map.get(tip, "int")
        
    def op_set(self, var, val, tip):
        """SET operation: Assign value to variable"""
        self.logger.log(f"SET {var} = {val} (type: {tip})", Fore.MAGENTA)
        
        # Vérifier si c'est une constante
        if var in self.constants:
            raise CompilerError(f"Cannot reassign constant '{var}'", self.current_line)
        
        if tip == "IDENT":
            self._check_var_exists(val)
            # Déterminer le type source (variable ou constante)
            if val in self.constants:
                source_type = self.constants[val]["type"]
            else:
                source_type = self.variables[val]["type"]
            
            if var in self.variables:
                if self.variables[var]["type"] != source_type:
                    raise CompilerError(
                        f"Cannot reassign '{var}' with different type. Declared as {self.variables[var]['type']}, got {source_type}",
                        self.current_line
                    )
                self.add_line(f"{var} = {val};")
            else:
                self.variables[var] = {"type": source_type}
                c_type = self._get_c_type(source_type)
                self.add_line(f"{c_type} {var} = {val};")
        else:
            if var in self.variables:
                if self.variables[var]["type"] != tip:
                    raise CompilerError(
                        f"Cannot reassign '{var}' with different type. Declared as {self.variables[var]['type']}, got {tip}",
                        self.current_line
                    )
                if tip == "STR":
                    self.add_line(f'{var} = "{val}";')
                else:
                    self.add_line(f"{var} = {val};")
            else:
                self.variables[var] = {"type": tip}
                c_type = self._get_c_type(tip)
                if tip == "STR":
                    self.add_line(f'{c_type} {var} = "{val}";')
                else:
                    self.add_line(f"{c_type} {var} = {val};")
        
        self.logger.success(f"Variable '{var}' set to {val}")
    
    def _get_operand_type(self, op, op_type):
        """Determine the actual type of an operand"""
        if op_type == "IDENT":
            self._check_var_exists(op)
            if op in self.constants:
                return self.constants[op]["type"]
            return self.variables[op]["type"]
        return op_type
    
    def _determine_result_type(self, op1, op2, op1_type, op2_type):
        """Determine result type for arithmetic operations"""
        actual_type1 = self._get_operand_type(op1, op1_type)
        actual_type2 = self._get_operand_type(op2, op2_type)
        
        if actual_type1 == "STR" or actual_type2 == "STR":
            raise CompilerError("Cannot perform arithmetic on strings", self.current_line)
        
        if actual_type1 == "FLOAT" or actual_type2 == "FLOAT":
            return "FLOAT"
        
        return "INT"
    
    def op_add(self, op1, op2, to, op1_type=None, op2_type=None):
        """ADD operation: op1 + op2 -> to"""
        self.logger.log(f"ADD {op1} + {op2} -> {to}", Fore.MAGENTA)
        
        result_type = self._determine_result_type(op1, op2, op1_type or "INT", op2_type or "INT")
        
        if to not in self.variables:
            self.variables[to] = {"type": result_type}
            c_type = self._get_c_type(result_type)
            to_decl = f"{c_type} {to}"
        else:
            to_decl = to
            
        self.add_line(f"{to_decl} = {op1} + {op2};")
        self.logger.success(f"Result stored in '{to}'")
    
    def op_sub(self, op1, op2, to, op1_type=None, op2_type=None):
        """SUB operation: op1 - op2 -> to"""
        self.logger.log(f"SUB {op1} - {op2} -> {to}", Fore.MAGENTA)
        
        result_type = self._determine_result_type(op1, op2, op1_type or "INT", op2_type or "INT")
        
        if to not in self.variables:
            self.variables[to] = {"type": result_type}
            c_type = self._get_c_type(result_type)
            to_decl = f"{c_type} {to}"
        else:
            to_decl = to
            
        self.add_line(f"{to_decl} = {op1} - {op2};")
        self.logger.success(f"Result stored in '{to}'")
    
    def op_mul(self, op1, op2, to, op1_type=None, op2_type=None):
        """MUL operation: op1 * op2 -> to"""
        self.logger.log(f"MUL {op1} * {op2} -> {to}", Fore.MAGENTA)
        
        result_type = self._determine_result_type(op1, op2, op1_type or "INT", op2_type or "INT")
        
        if to not in self.variables:
            self.variables[to] = {"type": result_type}
            c_type = self._get_c_type(result_type)
            to_decl = f"{c_type} {to}"
        else:
            to_decl = to
            
        self.add_line(f"{to_decl} = {op1} * {op2};")
        self.logger.success(f"Result stored in '{to}'")
    
    def op_div(self, op1, op2, to, op1_type=None, op2_type=None):
        """DIV operation: op1 / op2 -> to"""
        self.logger.log(f"DIV {op1} / {op2} -> {to}", Fore.MAGENTA)
        
        result_type = self._determine_result_type(op1, op2, op1_type or "INT", op2_type or "INT")
        
        if to not in self.variables:
            self.variables[to] = {"type": result_type}
            c_type = self._get_c_type(result_type)
            to_decl = f"{c_type} {to}"
        else:
            to_decl = to
        
        if result_type == "FLOAT":
            self.add_line(f"{to_decl} = {op2} != 0 ? {op1} / {op2} : 0.0;")
        else:
            self.add_line(f"{to_decl} = {op2} != 0 ? {op1} / {op2} : 0;")
        
        self.logger.success(f"Result stored in '{to}'")
    
    def op_mod(self, op1, op2, to, op1_type=None, op2_type=None):
        """MOD operation: op1 % op2 -> to (integers only)"""
        self.logger.log(f"MOD {op1} % {op2} -> {to}", Fore.MAGENTA)
        
        actual_type1 = self._get_operand_type(op1, op1_type or "INT")
        actual_type2 = self._get_operand_type(op2, op2_type or "INT")
        
        if actual_type1 == "FLOAT" or actual_type2 == "FLOAT":
            raise CompilerError("Modulo operation not supported for FLOAT types", self.current_line)
        
        if to not in self.variables:
            self.variables[to] = {"type": "INT"}
            to_decl = "int " + to
        else:
            to_decl = to
            
        self.add_line(f"{to_decl} = {op2} != 0 ? {op1} % {op2} : 0;")
        self.logger.success(f"Result stored in '{to}'")
    
    def op_show(self, op1, tipe, end, tipe_end):
        """SHOW operation: Print value"""
        self.logger.log(f"SHOW {op1} (type: {tipe})", Fore.MAGENTA)
        
        end_str = end if tipe_end == "STR" else "\\n"
        
        if tipe == "INT":
            self.add_line(f'printf("%d{end_str}", {op1});')
        elif tipe == "FLOAT":
            self.add_line(f'printf("%f{end_str}", {op1});')
        elif tipe == "BOOL":
            self.add_line(f'printf("%d{end_str}", {op1});')
        elif tipe == "STR":
            self.add_line(f'printf("%s{end_str}", "{op1}");')
        elif tipe == "IDENT":
            self._check_var_exists(op1)
            
            # CORRECTION: Chercher le type dans les variables OU les constantes
            if op1 in self.constants:
                var_type = self.constants[op1]["type"]
            else:
                var_type = self.variables[op1]["type"]
            
            if var_type == "INT" or var_type == "BOOL":
                self.add_line(f'printf("%d{end_str}", {op1});')
            elif var_type == "FLOAT":
                self.add_line(f'printf("%f{end_str}", {op1});')
            else:
                self.add_line(f'printf("%s{end_str}", {op1});')
        
        self.logger.success("Output generated")
    
    def op_cmp(self, op1, op2, cmp, to, op1t, op2t):
        """CMP operation: Compare op1 and op2, store result in to"""
        self.logger.log(f"CMP {op1} {cmp} {op2} -> {to}", Fore.MAGENTA)
        
        if op1t == "STR":
            op1 = f'"{op1}"'
        if op2t == "STR":
            op2 = f'"{op2}"'
        
        if op1t == "IDENT":
            self._check_var_exists(op1)
            op1t = self.variables[op1]["type"]

        if op2t == "IDENT":
            self._check_var_exists(op2)
            op2t = self.variables[op2]["type"]

        if op2t == "STR" and op1t != op2t:
            raise CompilerError("Cannot compare string with non-string", self.current_line)
            
        if to not in self.variables:
            self.variables[to] = {"type": "INT"}
            to_decl = "int " + to
        else:
            to_decl = to
        
        valid_operators = ["==", "!=", "<", ">", "<=", ">="]
        if cmp not in valid_operators:
            raise CompilerError(f"Invalid comparison operator '{cmp}'", self.current_line)
        
        if op1t == "STR" and op2t == "STR":
            if cmp != "==":
                raise CompilerError("Only == comparison supported for strings", self.current_line)
            self.add_line(f"{to_decl} = strcmp({op1}, {op2}) == 0;")
        else:
            self.add_line(f"{to_decl} = {op1} {cmp} {op2};")
        
        self.logger.success(f"Comparison result stored in '{to}'")
        
    def op_if(self, condition):
        """IF operation: Conditional execution"""
        self.logger.log(f"IF {condition}", Fore.MAGENTA)
        self.add_line(f"if ({condition}) {{")
        self.logger.success("Conditional block opened")
        return "IF_OPEN"
    
    def op_else(self):
        """ELSE operation: Alternative execution"""
        self.logger.log("ELSE", Fore.MAGENTA)
        self.add_line("} else {")
        self.logger.success("Else block opened")
        return "ELSE_OPEN"
    
    def op_endif(self):
        """ENDIF operation: Close conditional block"""
        self.logger.log("ENDIF", Fore.MAGENTA)
        self.add_line("}")
        self.logger.success("Conditional block closed")
    
    def op_label(self, name):
        """LABEL operation: Define label"""
        name = f"Label_{name}"
        self.logger.log(f"LABEL {name}", Fore.MAGENTA)
        self.add_line(f"{name}:")
        self.labels[name] = True
        self.logger.success(f"Label '{name}' defined")
        
    def op_go(self, to):
        """GOTO operation: Jump to label"""
        to = f"Label_{to}"
        self.logger.log(f"GOTO {to}", Fore.MAGENTA)
        self.add_line(f"goto {to};")
        if to not in self.labels:
            self.labels[to] = False
        self.logger.success(f"Jump to label '{to}'")
        
    def op_end(self, cdn):
        """END operation: Exit program"""
        self.logger.log("END", Fore.MAGENTA)
        self.add_line(f"exit({cdn});")

    def op_func(self, name, *args):
        """FUNC operation: Define function"""
        self.logger.log(f"FUNC {name} with args: {args}", Fore.MAGENTA)
        
        func_name = f"Func_{name}"
        # Remove the duplicate check - pass_one already validates this
        # if func_name in self.functions:
        #     raise CompilerError(f"Function '{name}' already defined", self.current_line)
        
        self.in_function = True
        self.current_function = func_name
        
        # Initialize function metadata if not already present
        if func_name not in self.functions:
            self.functions[func_name] = {"type": "VOID", "args": []}
        
        # Préparer les arguments
        arg_list = []
        for arg in args:
            arg_name = list(arg.values())[0]
            # Type par défaut pour les arguments
            arg_list.append(f"int {arg_name}")
            self.variables[arg_name] = {"type": "INT"}
            self.functions[func_name]["args"].append(arg_name)
        
        args_str = ", ".join(arg_list) if arg_list else "void"
        
        # On ne connaît pas encore le type de retour, on utilisera void par défaut
        self.add_line(f"void {func_name}({args_str}) {{")
        self.logger.success(f"Function '{name}' opened")
    
    def op_ret(self, value, value_type):
        """RET operation: Return from function"""
        self.logger.log(f"RET {value} (type: {value_type})", Fore.MAGENTA)
        
        if not self.in_function:
            raise CompilerError("Return outside function", self.current_line)
        
        # Déterminer le type de retour
        if value_type == "IDENT":
            self._check_var_exists(value)
            ret_type = self.variables[value]["type"]
        else:
            ret_type = value_type
        
        # Mettre à jour le type de la fonction
        if self.functions[self.current_function]["type"] == "VOID":
            self.functions[self.current_function]["type"] = ret_type
        elif self.functions[self.current_function]["type"] != ret_type:
            raise CompilerError(
                f"Return type mismatch in function '{self.current_function}'. "
                f"Expected {self.functions[self.current_function]['type']}, got {ret_type}",
                self.current_line
            )
        
        if value_type == "STR":
            self.add_line(f'return "{value}";')
        else:
            self.add_line(f"return {value};")
        
        self.logger.success("Return statement added")
    
    def op_endfunc(self):
        """ENDFUNC operation: Close function definition"""
        self.logger.log("ENDFUNC", Fore.MAGENTA)
        
        if not self.in_function:
            raise CompilerError("ENDFUNC outside function", self.current_line)
        
        self.add_line("}")
        
        # Corriger la signature de la fonction avec le bon type de retour
        func_type = self.functions[self.current_function]["type"]
        c_type = self._get_c_type(func_type)
        
        # Trouver et remplacer la déclaration de fonction
        for i, line in enumerate(self.function_code):
            if f"void {self.current_function}(" in line:
                self.function_code[i] = line.replace("void", c_type, 1)
                break
        
        self.in_function = False
        self.current_function = None
        self.logger.success("Function closed")
        
    def op_call(self, func_name, args, result_var=None):
        """CALL operation: Call a function"""
        self.logger.log(f"CALL {func_name} with {len(args)} args", Fore.MAGENTA)
        
        # 1. Vérifier que la fonction existe
        full_func_name = f"Func_{func_name}"
        if full_func_name not in self.functions:
            raise CompilerError(
                f"Function '{func_name}' not defined", 
                self.current_line
            )
        
        # 2. Vérifier le nombre d'arguments
        expected_args = len(self.functions[full_func_name]["args"])
        if len(args) != expected_args:
            raise CompilerError(
                f"Function '{func_name}' expects {expected_args} arguments, got {len(args)}",
                self.current_line
            )
        
        # 3. Préparer les arguments pour l'appel C
        c_args = []
        for arg in args:
            arg_value = list(arg.values())[0]
            arg_type = list(arg.keys())[0]
            
            # Si c'est une chaîne littérale, ajouter les guillemets
            if arg_type == "STR":
                c_args.append(f'"{arg_value}"')
            # Si c'est une variable, vérifier qu'elle existe
            elif arg_type == "IDENT":
                self._check_var_exists(arg_value)
                c_args.append(arg_value)
            # Sinon, utiliser la valeur directement
            else:
                c_args.append(str(arg_value))
        
        args_str = ", ".join(c_args)
        
        # 4. Générer l'appel de fonction
        func_return_type = self.functions[full_func_name]["type"]
        
        # Si la fonction retourne void (ne retourne rien)
        if func_return_type == "VOID":
            if result_var:
                raise CompilerError(
                    f"Function '{func_name}' does not return a value",
                    self.current_line
                )
            self.add_line(f"{full_func_name}({args_str});")
        
        # Si la fonction retourne une valeur
        else:
            if not result_var:
                # Appel sans récupération du résultat (warning optionnel)
                self.add_line(f"{full_func_name}({args_str});")
            else:
                # Créer ou réutiliser la variable de résultat
                if result_var not in self.variables:
                    self.variables[result_var] = {"type": func_return_type}
                    c_type = self._get_c_type(func_return_type)
                    self.add_line(f"{c_type} {result_var} = {full_func_name}({args_str});")
                else:
                    # Vérifier la compatibilité des types
                    if self.variables[result_var]["type"] != func_return_type:
                        raise CompilerError(
                            f"Type mismatch: variable '{result_var}' is {self.variables[result_var]['type']}, "
                            f"but function returns {func_return_type}",
                            self.current_line
                        )
                    self.add_line(f"{result_var} = {full_func_name}({args_str});")
        
        self.logger.success(f"Function call to '{func_name}' generated")

    def op_cst(self, cst, val, tip):
        """CST operation: Define a constant"""
        self.logger.log(f"CONST {cst} = {val} (type: {tip})", Fore.MAGENTA)
        
        # Vérifier si la constante existe déjà
        if cst in self.constants:
            raise CompilerError(f"Constant '{cst}' already defined", self.current_line)
        
        # CORRECTION: Vérifier aussi dans les variables
        if cst in self.variables:
            raise CompilerError(f"'{cst}' already declared as variable", self.current_line)
        
        # Enregistrer la constante
        self.constants[cst] = {"type": tip, "value": val}
        
        # Générer le code C
        c_type = self._get_c_type(tip)
        if tip == "STR":
            self.add_line(f'const {c_type} {cst} = "{val}";')
        else:
            self.add_line(f'const {c_type} {cst} = {val};')
        
        self.logger.success(f"Constant '{cst}' defined")
    
    def pass_one(self, lex_lines):
        """First pass: collect labels and function declarations"""
        self.logger.info("Starting pass one...")
        
        func_stack = []
        
        for line_num, tokens in lex_lines:
            if not tokens:
                continue
                
            op = list(tokens[0].values())[0]
            
            if op == "LBL":
                label_name = f"Label_{tokens[1]['IDENT']}"
                if label_name in self.labels and self.labels[label_name] == True:
                    raise CompilerError(f"Label '{tokens[1]['IDENT']}' already defined", line_num)
                self.labels[label_name] = True
                
            elif op == "GO":
                label_name = f"Label_{tokens[1]['IDENT']}"
                if label_name not in self.labels:
                    self.labels[label_name] = False
                    
            elif op == "FUNC":
                func_name = f"Func_{tokens[1]['IDENT']}"
                if func_name in self.functions:
                    raise CompilerError(f"Function '{tokens[1]['IDENT']}' already defined", line_num)
                self.functions[func_name] = {"type": "VOID", "args": []}
                func_stack.append(func_name)
                
            elif op == "RET":
                if not func_stack:
                    raise CompilerError("Return outside function", line_num)
                    
            elif op == "ENDFUNC":
                if not func_stack:
                    raise CompilerError("ENDFUNC without matching FUNC", line_num)
                func_stack.pop()
                
            elif op == "CALL":
                func_name = f"Func_{tokens[1]['IDENT']}"
                # On ne fait rien ici, la validation sera faite en pass 2
                # Mais on pourrait vérifier que la fonction existe
        
        if func_stack:
            raise CompilerError(f"Unclosed function: {func_stack[-1]}")
        
        # Vérifier que tous les labels référencés sont définis
        for label, defined in self.labels.items():
            if not defined:
                raise CompilerError(f"Label '{label}' referenced but not defined")
        
        self.logger.success("Pass one completed")

    def compile(self, tokens):
        """Main compilation dispatcher"""
        if not tokens:
            return None
        
        op = list(tokens[0].values())[0]
        self.logger.log(f"Processing opcode: {op}", Fore.YELLOW)
        self.logger.indent()
        
        try:
            if op == "SET":
                var = tokens[1]["IDENT"]
                val = list(tokens[2].values())[0]
                tip = list(tokens[2].keys())[0]
                self.op_set(var, val, tip)
                
            elif op == "ADD":
                op1 = list(tokens[1].values())[0]
                op2 = list(tokens[2].values())[0]
                to = list(tokens[3].values())[0]
                op1_type = list(tokens[1].keys())[0]
                op2_type = list(tokens[2].keys())[0]
                self.op_add(op1, op2, to, op1_type, op2_type)
                
            elif op == "SUB":
                op1 = list(tokens[1].values())[0]
                op2 = list(tokens[2].values())[0]
                to = list(tokens[3].values())[0]
                op1_type = list(tokens[1].keys())[0]
                op2_type = list(tokens[2].keys())[0]
                self.op_sub(op1, op2, to, op1_type, op2_type)
                
            elif op == "MUL":
                op1 = list(tokens[1].values())[0]
                op2 = list(tokens[2].values())[0]
                to = list(tokens[3].values())[0]
                op1_type = list(tokens[1].keys())[0]
                op2_type = list(tokens[2].keys())[0]
                self.op_mul(op1, op2, to, op1_type, op2_type)
                
            elif op == "DIV":
                op1 = list(tokens[1].values())[0]
                op2 = list(tokens[2].values())[0]
                to = list(tokens[3].values())[0]
                op1_type = list(tokens[1].keys())[0]
                op2_type = list(tokens[2].keys())[0]
                self.op_div(op1, op2, to, op1_type, op2_type)
                
            elif op == "MOD":
                op1 = list(tokens[1].values())[0]
                op2 = list(tokens[2].values())[0]
                to = list(tokens[3].values())[0]
                op1_type = list(tokens[1].keys())[0]
                op2_type = list(tokens[2].keys())[0]
                self.op_mod(op1, op2, to, op1_type, op2_type)
                
            elif op == "SHOW":
                try:
                    op1 = list(tokens[1].values())[0]
                    tipe = list(tokens[1].keys())[0]
                    end = list(tokens[2].values())[0] if len(tokens) > 2 else "\\n"
                    t_end = list(tokens[2].keys())[0] if len(tokens) > 2 else "STR"
                    self.op_show(op1, tipe, end, t_end)
                except IndexError:
                    raise CompilerError("Missing argument (SHOW <var> [<end>])", self.current_line)
                
            elif op == "CMP":
                op1 = list(tokens[1].values())[0]
                operator = list(tokens[2].values())[0]
                op2 = list(tokens[3].values())[0]
                to = list(tokens[4].values())[0]
                op1t = list(tokens[1].keys())[0]
                op2t = list(tokens[3].keys())[0]
                self.op_cmp(op1, op2, operator, to, op1t, op2t)
                
            elif op == "IF":
                condition = list(tokens[1].values())[0]
                return self.op_if(condition)
            
            elif op == "ELSE":
                return self.op_else()
            
            elif op == "ENDIF":
                self.op_endif()
                
            elif op == "LBL":
                name = list(tokens[1].values())[0]
                if list(tokens[1].keys())[0] != "IDENT":
                    raise CompilerError(f"Invalid label name '{name}'", self.current_line)
                self.op_label(name)
            
            elif op == "GO":
                name = list(tokens[1].values())[0]
                if list(tokens[1].keys())[0] != "IDENT":
                    raise CompilerError(f"Invalid label name '{name}'", self.current_line)
                self.op_go(name)
                
            elif op == "END":
                cdn = list(tokens[1].values())[0]
                if list(tokens[1].keys())[0] not in ["INT", "BOOL"]:
                    raise CompilerError(f"Invalid condition '{cdn}'", self.current_line)
                self.op_end(cdn)
                
            elif op == "FUNC":
                name = list(tokens[1].values())[0]
                if list(tokens[1].keys())[0] != "IDENT":
                    raise CompilerError(f"Invalid function name '{name}'", self.current_line)
                for arg in tokens[2:]:
                    if list(arg.keys())[0] != "IDENT":
                        raise CompilerError(f"Invalid argument name '{arg}'", self.current_line)
                self.op_func(name, *tokens[2:])
                
            elif op == "RET":
                value = list(tokens[1].values())[0]
                value_type = list(tokens[1].keys())[0]
                self.op_ret(value, value_type)
                
            elif op == "ENDFUNC":
                self.op_endfunc()
                
            elif op == "CALL":
                # Extraire le nom de la fonction
                if len(tokens) < 2:
                    raise CompilerError("CALL requires a function name", self.current_line)
                
                func_name = list(tokens[1].values())[0]
                if list(tokens[1].keys())[0] != "IDENT":
                    raise CompilerError(f"Invalid function name '{func_name}'", self.current_line)
                
                # Chercher "->" dans les tokens
                arrow_index = None
                for i in range(2, len(tokens)):
                    token_key = list(tokens[i].keys())[0]
                    token_val = list(tokens[i].values())[0]
                    
                    # Détecter "->" (peut être IDENT ou OPERATOR selon le lexer)
                    if (token_key == "IDENT" and token_val == "->") or \
                    (token_key == "OPERATOR" and token_val == "->"):
                        arrow_index = i
                        break
                
                # Extraire arguments et variable de résultat
                if arrow_index is not None:
                    # Il y a un "->"
                    args = tokens[2:arrow_index]  # Arguments avant la flèche
                    
                    # Variable de résultat après la flèche
                    if arrow_index + 1 >= len(tokens):
                        raise CompilerError("Expected variable name after '->'", self.current_line)
                    
                    result_var = list(tokens[arrow_index + 1].values())[0]
                    
                    if list(tokens[arrow_index + 1].keys())[0] != "IDENT":
                        raise CompilerError(f"Invalid result variable name '{result_var}'", self.current_line)
                else:
                    # Pas de "->"
                    args = tokens[2:]
                    result_var = None
                
                self.op_call(func_name, args, result_var)
            
            elif op == "CST":
                # CORRECTION: Gérer correctement les tokens
                if len(tokens) < 3:
                    raise CompilerError("CST requires name and value", self.current_line)
                
                cst_token = tokens[1]
                if "IDENT" not in cst_token:
                    raise CompilerError("CST name must be an identifier", self.current_line)
                
                cst = cst_token["IDENT"]
                val = list(tokens[2].values())[0]
                tip = list(tokens[2].keys())[0]
                self.op_cst(cst, val, tip)
            
            else:
                raise CompilerError(f"Unknown opcode '{op}'", self.current_line)
                
        except IndexError as e:
            raise CompilerError(f"Missing arguments for opcode '{op}'", self.current_line)
        finally:
            self.logger.dedent()
        
        return op

def MLX(line):
    """Lexer: Tokenize a line of code"""
    line = line.strip()
    if not line:
        return []

    tokens = []
    i = 0
    n = len(line)
    buf = []
    in_quote = False
    quote_char = None

    # Opérateurs à reconnaître (AJOUT DE ->)
    operators = ['->', '==', '!=', '<=', '>=', '<', '>']  # <- ICI

    def flush_buf(as_quoted=False):
        nonlocal buf
        if not buf and not as_quoted:
            return
        tok = ''.join(buf)
        buf = []
        if as_quoted:
            tokens.append({"STR": tok})
        else:
            if tok == "True":
                tokens.append({"BOOL": 1})
            elif tok == "False":
                tokens.append({"BOOL": 0})
            elif tok.lstrip('+-').replace('.', '', 1).isdigit() and tok not in ('+', '-', '.'):
                if '.' in tok:
                    tokens.append({"FLOAT": float(tok)})
                else:
                    tokens.append({"INT": int(tok)})
            else:
                tokens.append({"IDENT": tok})

    while i < n:
        ch = line[i]

        if not in_quote and ch == '-' and i + 1 < n and line[i+1] == '-':
            break

        if ch in ('"', "'"):
            if not in_quote:
                if buf:
                    flush_buf(False)
                in_quote = True
                quote_char = ch
                buf = []
                i += 1
                continue
            else:
                if ch == quote_char:
                    in_quote = False
                    quote_char = None
                    flush_buf(as_quoted=True)
                    i += 1
                    continue
                else:
                    buf.append(ch)
                    i += 1
                    continue

        if in_quote:
            buf.append(ch)
            i += 1
            continue

        # Vérifier les opérateurs multi-caractères
        if not in_quote:
            found_op = False
            for op in operators:
                if line[i:i+len(op)] == op:
                    if buf:
                        flush_buf(False)
                    tokens.append({"OPERATOR": op})
                    i += len(op)
                    found_op = True
                    break
            if found_op:
                continue

        if ch.isspace():
            if buf:
                flush_buf(False)
            i += 1
            continue

        buf.append(ch)
        i += 1

    if in_quote:
        flush_buf(as_quoted=True)
    else:
        if buf:
            flush_buf(False)

    if not tokens:
        return []

    first_token = tokens[0]
    k, v = list(first_token.items())[0]
    out = [{"OP": v}]

    for t in tokens[1:]:
        out.append(t)
    return out

def main():
    parser = argparse.ArgumentParser(description="REX-C Compiler")
    parser.add_argument("-f", "--file", type=str, help="Source file", required=True)
    parser.add_argument("-o", "--output", type=str, help="Output file", required=False)
    parser.add_argument("-d", "--debug", action="store_true", help="Debug mode")
    parser.add_argument("-s", "--silent", action="store_true", help="Silent mode")
    parser.add_argument("-rs", "--real-silent", action="store_true", help="Real silent mode")
    parser.add_argument("-kc", "--keep-C", action="store_true", help="Keep C file")
    parser.add_argument("-r", "--run", action="store_true", help="Run after compile")
    parser.add_argument("-t", "--time", type=float, help="Time between each step", default=0.0)
    args = parser.parse_args()
    
    logger = DebugLogger(args.debug)
    compiler = REXCompiler(logger)
    
    try:
        logger.info(f"Reading source file: {args.file}")
        with open(args.file, "r") as f:
            code = f.read()
        
        logger.info("Lexical analysis...")
        Lex = []
        for line_num, line in enumerate(code.split("\n"), 1):
            tokens = MLX(line)
            Lex.append((line_num, tokens))
        
        if not Lex or not Lex[0][1]:
            raise CompilerError("Empty source file")
        
        Tag = Lex[0][1][1]["IDENT"]
        
        if Tag not in ["REX", "RED"]:
            raise CompilerError("First token must be REX or RED")
        
        logger.success(f"Mode: {Tag}")
        print(f"{Fore.CYAN}╔══════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║   REX-C Compiler - {Tag} Mode  ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════╝\n\n{Style.RESET_ALL}")
        
        non_empty = sum(1 for _, tokens in Lex[1:] if tokens)
        if non_empty == 0:
            non_empty = 1
            
        logger.info("Starting compilation...")
        
        logger.info("Pass 1...")
        
        compiler.pass_one(Lex[1:])
        
        logger.info("\n\nNow compiling...\n")
        
        p2 = ProgBar(non_empty, args.real_silent)
            
        for line_num, tokens in Lex[1:]:
            if not tokens:
                continue
            
            compiler.current_line = line_num
            logger.log(f"Line {line_num}: {tokens}", Fore.WHITE)
            
            compiler.compile(tokens)
            
            time.sleep(args.time)
            
            if not args.debug and not args.real_silent:
                p2.increment()
                p2.show()
                
        compiler.check_label_exists()
        
        if not args.debug and not args.real_silent:
            p2.show(force=True)
            print()
            
        output_name = args.output or (
            args.file.split(".")[0] if not args.file.startswith(".") 
            else args.file.split(".")[1].replace("/", "")
        )
        
        logger.info("Finalizing C code...")
        c_code = compiler.finalize()
        
        with open(f"{output_name}_tmp.c", "w") as f:
            f.write(c_code)
        
        logger.success(f"C code generated: {output_name}_tmp.c")
        
        logger.info(f"Compiling to {output_name}...")
        result = os.system(f"gcc {output_name}_tmp.c -o {output_name} 2>&1")
        
        if result != 0:
            raise CompilerError("GCC compilation failed")
        
        if not args.keep_C:
            os.remove(f"{output_name}_tmp.c")
            logger.info("Removed temporary C file")
        
        if not args.real_silent and not args.silent:
            print(f"{Fore.GREEN}✓ Compilation successful: {output_name}{Style.RESET_ALL}")
        
        if args.run:
            logger.info(f"Executing {output_name}...")
            print(f"\n{Fore.CYAN}{'═' * 40}{Style.RESET_ALL}")
            os.system(f"./{output_name}")
            print(f"{Fore.CYAN}{'═' * 40}{Style.RESET_ALL}")
    
    except CompilerError as e:
        e.display()
        sys.exit(1)
    except FileNotFoundError:
        print(f"{Fore.RED}Error: File '{args.file}' not found{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
