python cli.py run "What is 17 to the power of 4?" --stream --verbose
python cli.py run "Write a Python one-liner that reverses a string" --model qwen2.5-coder:0.5b-instruct-q4_k_m --stream --verbose
python cli.py run "Give me 5 variable naming conventions with examples" --verbose
python cli.py run "What is sqrt(1764)?" --tools calculator --verbose
python cli.py run "How many seconds are in a year?" --tools calculator --verbose
python cli.py run "What is 2 to the power of 32?" --tools calculator --verbose
python cli.py run "How many Python files are in the current directory?" --tools shell --verbose
python cli.py run "What is my current working directory and username?" --tools shell --verbose
python cli.py run "How much disk space is free?" --tools shell --verbose
python cli.py run "List the files in the examples/ folder" --tools list_directory --verbose
python cli.py run "Read the file examples/01_basic_agent.py and summarize what it does" --tools read_file --verbose
python cli.py run "Write a file called hello.txt with the content 'Hello from LocalClaw!'" --tools write_file --verbose
python cli.py run "Generate the first 10 Fibonacci numbers" --tools python_repl --verbose
python cli.py run "What is the md5 hash of the string 'localclaw'?" --tools python_repl --verbose
python cli.py run "Write a fibonacci function to hello.txt then read it back" --tools write_file,read_file --verbose
python cli.py run "Calculate compound interest: $1000 at 5% for 20 years compounded monthly" --tools calculator --verbose