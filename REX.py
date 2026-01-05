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
            "#include <string.h>",
            "int main() {"
        ]
        self.variables = {}
        self.labels = {}
        self.logger = debug_logger
        self.current_line = 0
        self.skip_next = False  # Pour gérer le IF
        
    def add_line(self, code):
        self.c_code.append(code)
        
    def finalize(self):
        self.c_code.append("return 0;}")
        return "\n".join(self.c_code)
    
    def _check_var_exists(self, var):
        if var not in self.variables:
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
        
    def op_set(self, var, val, tip):
        """SET operation: Assign value to variable"""
        self.logger.log(f"SET {var} = {val} (type: {tip})", Fore.MAGENTA)
        
        # If assigning from another variable (IDENT type)
        if tip == "IDENT":
            # Check that source variable exists
            self._check_var_exists(val)
            source_type = self.variables[val]["type"]
            
            if var in self.variables:
                # Check type compatibility
                if self.variables[var]["type"] != source_type:
                    raise CompilerError(
                        f"Cannot reassign '{var}' with different type. Declared as {self.variables[var]['type']}, got {source_type}",
                        self.current_line
                    )
                self.add_line(f"{var} = {val};")
            else:
                # Create new variable with same type as source
                self.variables[var] = {"type": source_type}
                if source_type == "INT":
                    self.add_line(f"int {var} = {val};")
                else:  # STR
                    self.add_line(f"char* {var} = {val};")
        else:
            # Original logic for literal values
            if var in self.variables:
                if self.variables[var]["type"] != tip:
                    raise CompilerError(
                        f"Cannot reassign '{var}' with different type. Declared as {self.variables[var]['type']}, got {tip}",
                        self.current_line
                    )
                if tip == "INT":
                    self.add_line(f"{var} = {val};")
                else:  # STR
                    self.add_line(f'{var} = "{val}";')
            else:
                self.variables[var] = {"type": tip}
                if tip == "INT":
                    self.add_line(f"int {var} = {val};")
                else:  # STR
                    self.add_line(f'char* {var} = "{val}";')
        
        self.logger.success(f"Variable '{var}' set to {val}")
    def op_add(self, op1, op2, to):
        """ADD operation: op1 + op2 -> to"""
        self.logger.log(f"ADD {op1} + {op2} -> {to}", Fore.MAGENTA)
        
        if to in self.variables:
            self._check_var_type(to, "INT")
            self.add_line(f"{to} = {op1} + {op2};")
        else:
            self.variables[to] = {"type": "INT"}
            self.add_line(f"int {to} = {op1} + {op2};")
        
        self.logger.success(f"Result stored in '{to}'")
    
    def op_sub(self, op1, op2, to):
        """SUB operation: op1 - op2 -> to"""
        self.logger.log(f"SUB {op1} - {op2} -> {to}", Fore.MAGENTA)
        
        if to in self.variables:
            self._check_var_type(to, "INT")
            self.add_line(f"{to} = {op1} - {op2};")
        else:
            self.variables[to] = {"type": "INT"}
            self.add_line(f"int {to} = {op1} - {op2};")
        
        self.logger.success(f"Result stored in '{to}'")
    
    def op_mul(self, op1, op2, to):
        """MUL operation: op1 * op2 -> to"""
        self.logger.log(f"MUL {op1} * {op2} -> {to}", Fore.MAGENTA)
        
        if to in self.variables:
            self._check_var_type(to, "INT")
            self.add_line(f"{to} = {op1} * {op2};")
        else:
            self.variables[to] = {"type": "INT"}
            self.add_line(f"int {to} = {op1} * {op2};")
        
        self.logger.success(f"Result stored in '{to}'")
    
    def op_div(self, op1, op2, to):
        """DIV operation: op1 / op2 -> to"""
        self.logger.log(f"DIV {op1} / {op2} -> {to}", Fore.MAGENTA)
        
        if to in self.variables:
            self._check_var_type(to, "INT")
            self.add_line(f"{to} = {op1} / {op2};")
        else:
            self.variables[to] = {"type": "INT"}
            self.add_line(f"int {to} = {op2} != 0 ? {op1} / {op2} : 0;")
        
        self.logger.success(f"Result stored in '{to}'")
    
    def op_mod(self, op1, op2, to):
        """MOD operation: op1 % op2 -> to"""
        self.logger.log(f"MOD {op1} % {op2} -> {to}", Fore.MAGENTA)
        
        if to in self.variables:
            self._check_var_type(to, "INT")
            self.add_line(f"{to} = {op1} % {op2};")
        else:
            self.variables[to] = {"type": "INT"}
            self.add_line(f"int {to} = {op1} % {op2};")
        
        self.logger.success(f"Result stored in '{to}'")
    
    def op_show(self, op1, tipe, end, tipe_end):
        """SHOW operation: Print value"""
        self.logger.log(f"SHOW {op1} (type: {tipe})", Fore.MAGENTA)
        
        if tipe == "INT":
            end_str = end if tipe_end == "STR" else "\\n"
            self.add_line(f'printf("%d{end_str}", {op1});')
        elif tipe == "STR":
            end_str = end if tipe_end == "STR" else "\\n"
            self.add_line(f'printf("%s{end_str}", "{op1}");')
        elif tipe == "IDENT":
            self._check_var_exists(op1)
            var_type = self.variables[op1]["type"]
            end_str = end if tipe_end == "STR" else "\\n"
            
            if var_type == "INT":
                self.add_line(f'printf("%d{end_str}", {op1});')
            else:  # STR
                self.add_line(f'printf("%s{end_str}", {op1});')
        
        self.logger.success("Output generated")
    
    def op_cmp(self, op1, op2, cmp, to, op1t, op2t):
        """CMP operation: Compare op1 and op2, store result in to"""
        self.logger.log(f"CMP {op1} {cmp} {op2} -> {to}", Fore.MAGENTA)
        t = "INT"
        
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
        if op1t == "STR" and op2t == "STR":
            t = "STR"
            
        if to not in self.variables:
            self.variables[to] = {"type": "INT"}
            to = f"int {to}"
        
        valid_operators = ["==", "!=", "<", ">", "<=", ">="]
        if cmp not in valid_operators:
            raise CompilerError(f"Invalid comparison operator '{cmp}'", self.current_line)
        
        if t == "INT":
            self.add_line(f"{to} = {op1} {cmp} {op2};")
        else: 
            if cmp != "==":
                raise CompilerError("Invalid comparison operator for strings", self.current_line)
            self.add_line(f"{to} = strcmp({op1}, {op2}) == 0;")
        
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
        self.logger.log(f"LABEL {name}", Fore.MAGENTA)
        self.add_line(f"{name}:")
        self.labels[name] = True
        self.logger.success(f"Label '{name}' defined")
        
    def op_go(self, to):
        """GOTO operation: Jump to label"""
        self.logger.log(f"GOTO {to}", Fore.MAGENTA)
        self.add_line(f"goto {to};")
        if to not in self.labels: self.labels[to] = False
        self.logger.success(f"Jump to label '{to}'")
        
    def op_end(self, cdn):
        self.logger.log("END", Fore.MAGENTA)
        self.add_line(f"exit({cdn});")        

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
                self.op_add(op1, op2, to)
                
            elif op == "SUB":
                op1 = list(tokens[1].values())[0]
                op2 = list(tokens[2].values())[0]
                to = list(tokens[3].values())[0]
                self.op_sub(op1, op2, to)
                
            elif op == "MUL":
                op1 = list(tokens[1].values())[0]
                op2 = list(tokens[2].values())[0]
                to = list(tokens[3].values())[0]
                self.op_mul(op1, op2, to)
                
            elif op == "DIV":
                op1 = list(tokens[1].values())[0]
                op2 = list(tokens[2].values())[0]
                to = list(tokens[3].values())[0]
                self.op_div(op1, op2, to)
                
            elif op == "MOD":
                op1 = list(tokens[1].values())[0]
                op2 = list(tokens[2].values())[0]
                to = list(tokens[3].values())[0]
                self.op_mod(op1, op2, to)
                
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
                op2 = list(tokens[3].values())[0]
                operator = list(tokens[2].values())[0]
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
                if name in self.labels and self.labels[name] == True:
                    raise CompilerError(f"Label '{name}' already defined", self.current_line)
                self.op_label(name)
            
            elif op == "GO":
                name = list(tokens[1].values())[0]
                if list(tokens[1].keys())[0] != "IDENT":
                    raise CompilerError(f"Invalid label name '{name}'", self.current_line)
                self.op_go(name)
                
            elif op == "END":
                cdn = list(tokens[1].values())[0]
                if list(tokens[1].keys())[0] != "INT":
                    raise CompilerError(f"Invalid condition '{cdn}'", self.current_line)
                self.op_end(cdn)
                
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

    def flush_buf(as_quoted=False):
        nonlocal buf
        if not buf and not as_quoted:
            return
        tok = ''.join(buf)
        buf = []
        if as_quoted:
            tokens.append({"STR": tok})
        else:
            # Gestion des booléens
            if tok == "True":
                tokens.append({"BOOL": 1})
            elif tok == "False":
                tokens.append({"BOOL": 0})
            # Gestion des nombres (int et float)
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
        print(f"{Fore.CYAN}╚══════════════════════════════╝{Style.RESET_ALL}")
        
        non_empty = sum(1 for _, tokens in Lex[1:] if tokens)
        if non_empty == 0:
            non_empty = 1
        p = ProgBar(non_empty, args.real_silent)
        
        logger.info("Starting compilation...")
        for line_num, tokens in Lex[1:]:
            if not tokens:
                continue
            
            compiler.current_line = line_num
            logger.log(f"Line {line_num}: {tokens}", Fore.WHITE)
            
            compiler.compile(tokens)
            
            time.sleep(args.time)
            
            if not args.debug and not args.real_silent:
                p.increment()
                p.show()
                
        compiler.check_label_exists()
        
        if not args.debug and not args.real_silent:
            p.show(force=True)
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